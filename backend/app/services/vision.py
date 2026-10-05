"""Two-stage product recognition: OCR -> vision understanding -> sanitized fields.

Pipeline:
  preprocess image (EXIF + downscale) -> OCR model (extract readable text)
  -> vision model (understand product + map to Product fields) -> sanitize.

This module never touches the database and never returns provider secrets.
"""
import base64
import asyncio
import ctypes
import io
import json
import logging
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache, partial
from pathlib import Path
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Pillow's decode/resize/encode work is CPU-bound.  Running it inline in an
# async endpoint blocks every request on this Uvicorn worker; a bounded,
# dedicated pool lets network-bound OCR/vision calls continue while avoiding a
# burst of photo uploads consuming unbounded CPU.
_IMAGE_PREPROCESS_EXECUTOR = ThreadPoolExecutor(
    max_workers=settings.IMAGE_PREPROCESS_MAX_WORKERS,
    thread_name_prefix="image-preprocess",
)


@lru_cache(maxsize=4)
def _load_native_image_library(path: str):
    if not Path(path).is_file():
        return None
    try:
        library = ctypes.CDLL(path)
        library.qp_preprocess_image.argtypes = [
            ctypes.c_char_p, ctypes.c_size_t, ctypes.c_int, ctypes.c_int,
            ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_size_t),
        ]
        library.qp_preprocess_image.restype = ctypes.c_int
        library.qp_free_image.argtypes = [ctypes.c_void_p]
        library.qp_free_image.restype = None
        return library
    except (OSError, AttributeError):
        logger.warning("C++ image library unavailable; using Pillow")
        return None


def _call_native_image_library(image_bytes: bytes, max_dimension: int, quality: int) -> bytes | None:
    path = settings.NATIVE_IMAGE_PREPROCESSOR_LIBRARY.strip()
    if not path:
        return None
    library = _load_native_image_library(path)
    if library is None:
        return None
    output = ctypes.c_void_p()
    output_size = ctypes.c_size_t()
    try:
        result = library.qp_preprocess_image(
            image_bytes, len(image_bytes), max_dimension, quality,
            ctypes.byref(output), ctypes.byref(output_size),
        )
        if result != 0 or not output.value or not (0 < output_size.value <= 20 * 1024 * 1024):
            logger.warning("C++ image library rejected input; using Pillow")
            return None
        return ctypes.string_at(output.value, output_size.value)
    finally:
        if output.value:
            library.qp_free_image(output)


def _try_native_preprocess(
    image_bytes: bytes,
    max_dimension: int,
    quality: int,
    *,
    use_library: bool = True,
) -> tuple[bytes, str, tuple[int, int]] | None:
    """Try configured C++ library or native subprocess; preserve Pillow fallback."""
    executable = settings.NATIVE_IMAGE_PREPROCESSOR_PATH.strip()
    library_path = settings.NATIVE_IMAGE_PREPROCESSOR_LIBRARY.strip() if use_library else ""
    if not executable and not library_path:
        return None

    try:
        output = _call_native_image_library(image_bytes, max_dimension, quality) if use_library else None
        if output is None and executable:
            completed = subprocess.run(
                [
                    executable,
                    "--max-dimension", str(max_dimension),
                    "--quality", str(quality),
                ],
                input=image_bytes,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=settings.NATIVE_IMAGE_PREPROCESS_TIMEOUT,
                check=False,
            )
            if completed.returncode == 0:
                output = completed.stdout
            else:
                logger.warning(
                    "native image preprocessing failed (exit=%s, detail=%s); using Pillow",
                    completed.returncode,
                    completed.stderr.decode("utf-8", errors="replace")[:200],
                )
        if not output:
            return None

        from PIL import Image

        with Image.open(io.BytesIO(output)) as processed:
            processed.verify()
            size = processed.size
        if not size[0] or not size[1] or max(size) > max_dimension:
            logger.warning("native image preprocessing returned invalid dimensions; using Pillow")
            return None
        return output, "image/jpeg", size
    except Exception as exc:
        logger.warning("native image preprocessing unavailable (%s); using Pillow", type(exc).__name__)
        return None

ALLOWED_CATEGORIES = {
    "led_lighting", "electronics", "machinery", "textiles",
    "furniture", "packaging", "auto_parts", "hardware", "other",
}

# Field length caps matching the Product model / schema.
_LEN_NAME = 300
_LEN_SKU = 100
_LEN_CERTS = 500
_LEN_TEXT = 5000

_FIELD_KEYS = [
    "name", "sku", "category", "description", "technical_specs",
    "certifications", "moq", "unit_price", "price_range_low",
    "price_range_high", "pricing", "lead_time_days",
]

OCR_SYSTEM_PROMPT = """You are a high-precision OCR engine specialized in product nameplates, specification labels, parameter tables, and packaging text for international trade.

Task: FAITHFULLY TRANSCRIBE every readable character in the image. You are READING, not understanding or reasoning about the product.

Transcribe ALL visible text, including:
- Product name, model, SKU, part number, item number, product number, serial number.
- Technical parameters WITH their values and units: voltage, wattage, power, current, frequency, dimensions, weight, capacity, material, color, luminous flux, IP rating, etc.
- Certification marks and adjacent text/numbers: CE, RoHS, UL, FCC, ETL, CCC, PSE, KC, SAA, BIS, etc.
- Specification tables: preserve rows and columns as faithfully as possible.
- Mixed Chinese and English text: keep both, do not drop either.
- Packaging labels, barcode digits, country of origin, "Made in ...".

Strict rules:
- Preserve the original text EXACTLY. Do NOT translate, transliterate, summarize, paraphrase, reorder, or "correct" anything.
- Preserve digits, units, symbols, case, hyphens, slashes, parentheses, decimal points, and line/paragraph structure.
- Keep SKU / model / part-number strings character-for-character (e.g. "HX-LED-24V-12W" stays exactly that). Never insert, remove, or alter spaces, dashes, or digits.
- Do NOT "fix" visually similar characters (e.g. 0/O, 1/l/I, 5/S). Transcribe what is actually visible.
- If a character or word is blurred or illegible, SKIP it. Do NOT guess or complete partial text.
- Do NOT infer, deduce, or add any text that is not literally visible in the image.
- Do NOT output commentary, explanation, headings, or JSON. Output ONLY the recognized text, in natural reading order."""

VISION_SYSTEM_PROMPT = """You are a STRICT product-attribute extraction system for an international trade platform.

Evidence priority:
1. The ORIGINAL IMAGE is the highest-priority evidence.
2. The OCR text is supplementary evidence only.
3. If the OCR text conflicts with what is actually visible in the image, trust the IMAGE.
4. If something cannot be confirmed from either source, return null for that field.

Absolute prohibitions (to prevent hallucination):
- Do NOT use general product knowledge or common sense to infer ANY field.
- Do NOT complete, fill, or "enrich" fields that are not shown in the image/OCR.
- Do NOT guess MOQ, unit_price, price ranges, or lead_time_days from product category or typical values. These MUST be null unless explicitly visible (e.g. a price tag / MOQ label in the image or OCR).
- sku MUST come from a SKU/model/part-number string literally visible in the image or OCR. Never invent or fabricate a SKU.
- certifications MUST come from certification marks, logos, numbers, or text explicitly visible in the image/OCR. Never list certifications from general knowledge.
- Never output a field that is not in the schema below. Never fabricate brand, material, weight, dimensions, or any value not literally shown.
- When readable OCR text exists, preserve the language used in the image/OCR in every text-valued product field. Do NOT translate Chinese, Japanese, Korean, Arabic, or any other language into English (or translate English into another language).
- Keep original wording, terminology, symbols, and mixed-language text. The only exception is category, which is a fixed internal enum required by the schema.
- When there is NO readable text and the image contains only a product/object, use Simplified Chinese for text-valued fields. Identify only visually confirmable product attributes; do not invent model numbers, technical values, materials, or commercial claims.

Field rules:
- name: if readable text identifies the product, keep the original language and wording exactly. If there is no readable text, use a concise Simplified Chinese visual product name only when the object can be identified confidently; otherwise null.
- category: must be EXACTLY one of: led_lighting, electronics, machinery, textiles, furniture, packaging, auto_parts, hardware, other. Choose a category only if you can confirm it from the image. Otherwise null.
- technical_specs: compile ALL confirmable technical parameters from the image/OCR as structured text, one "key: value" item per line. Preserve the source language, wording, numbers, and units exactly as shown. Do not translate or invent specs.
- description: include ONLY product information confirmable from the image. Preserve the original source language when readable text exists; when there is no readable text, write the confirmed visual description in Simplified Chinese. No speculation.
- moq / unit_price / price_range_low / price_range_high / lead_time_days / pricing: null unless explicitly stated in the image or OCR.

Return ONLY valid JSON (no markdown, no code fences, no extra text) in exactly this shape (every field nullable):
{
  "name": null,
  "sku": null,
  "category": null,
  "description": null,
  "technical_specs": null,
  "certifications": null,
  "moq": null,
  "unit_price": null,
  "price_range_low": null,
  "price_range_high": null,
  "pricing": null,
  "lead_time_days": null
}
"""


# ── HTTP client (module-level, reused connection pool) ──────────────────────

_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0))
    return _client


async def close_ai_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


# ── JSON parse + sanitize ───────────────────────────────────────────────────

def _parse_json(text: str) -> dict[str, Any]:
    """Parse model output to JSON, tolerating markdown fences. Never raises."""
    if not isinstance(text, str):
        return {}
    text = text.strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
        return {}
    except json.JSONDecodeError:
        pass
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if m:
        try:
            data = json.loads(m.group(1))
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            pass
    return {}


def _clean_str(value: Any, max_len: int) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value:
        return None
    return value[:max_len]


_NUM_RE = re.compile(r"^\s*[+]?\d+\s*$")
_FLOAT_RE = re.compile(r"^\s*[+]?\d+(?:\.\d+)?\s*$")


def _clean_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float) and value.is_integer() and value >= 0:
        return int(value)
    # Tolerate numeric strings the model sometimes emits in JSON (e.g. "100").
    # Non-numeric strings stay null — never coerced into fabricated numbers.
    if isinstance(value, str) and _NUM_RE.match(value):
        iv = int(value.strip())
        return iv if iv >= 0 else None
    return None


def _clean_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if value >= 0 else None
    if isinstance(value, str) and _FLOAT_RE.match(value):
        fv = float(value.strip())
        return fv if fv >= 0 else None
    return None


def _clean_category(value: Any) -> str | None:
    s = _clean_str(value, _LEN_SKU)
    if s is None:
        return None
    # Normalize case/spaces so a valid enum returned with different casing
    # (e.g. "LED Lighting") is still accepted; anything off-enum stays null.
    norm = s.lower().replace(" ", "_")
    return norm if norm in ALLOWED_CATEGORIES else None


def _empty_fields() -> dict[str, Any]:
    return {k: None for k in _FIELD_KEYS}


def sanitize_recognition(parsed: Any) -> dict[str, Any]:
    """Whitelist + coerce model output into safe, user-editable Product fields."""
    if not isinstance(parsed, dict):
        return _empty_fields()

    raw = parsed.get("fields") if isinstance(parsed.get("fields"), dict) else parsed

    return {
        "name": _clean_str(raw.get("name"), _LEN_NAME),
        "sku": _clean_str(raw.get("sku"), _LEN_SKU),
        "category": _clean_category(raw.get("category")),
        "description": _clean_str(raw.get("description"), _LEN_TEXT),
        "technical_specs": _clean_str(raw.get("technical_specs"), _LEN_TEXT),
        "certifications": _clean_str(raw.get("certifications"), _LEN_CERTS),
        "moq": _clean_int(raw.get("moq")),
        "unit_price": _clean_float(raw.get("unit_price")),
        "price_range_low": _clean_float(raw.get("price_range_low")),
        "price_range_high": _clean_float(raw.get("price_range_high")),
        "pricing": _clean_str(raw.get("pricing"), _LEN_TEXT),
        "lead_time_days": _clean_int(raw.get("lead_time_days")),
    }


# ── Image preprocessing ─────────────────────────────────────────────────────

def _preprocess(
    image_bytes: bytes,
    mime_type: str,
    max_dimension: int,
    quality: int,
) -> tuple[bytes, str, dict]:
    """EXIF-orient, optionally downscale large images, re-encode to JPEG.

    Returns (out_bytes, out_mime, meta) where meta carries original/processed
    dimensions, sizes and transform flags for telemetry. Accuracy-first:
    - Never upscale.
    - Pass through the original bytes verbatim when no transform is needed (no
      EXIF orientation, no downscale, already an RGB/L mode). This preserves the
      text edges of lossless sources (PNG spec sheets / screenshots) that a JPEG
      re-encode would blur.
    - When a transform is needed, re-encode JPEG at `quality` to trade payload
      size for small-character sharpness (configurable via settings).
    - On any error, the original bytes are returned unchanged.
    """
    ob = len(image_bytes)
    meta: dict[str, Any] = {
        "original_width": 0, "original_height": 0, "original_bytes": ob,
        "megapixels": 0.0, "was_resized": False, "was_reencoded": False,
        "processed_width": 0, "processed_height": 0, "processed_bytes": ob,
        "preprocess_backend": "original",
    }
    try:
        from PIL import Image, ImageOps

        img = Image.open(io.BytesIO(image_bytes))

        exif = img.getexif() if hasattr(img, "getexif") else None
        _ORIENTATION = 0x0112
        has_orientation = bool(
            exif and _ORIENTATION in exif and exif[_ORIENTATION] not in (1, None)
        )

        w, h = img.size
        needs_resize = bool(max_dimension) and max(w, h) > max_dimension
        meta.update(original_width=w, original_height=h,
                    megapixels=round((w * h) / 1_000_000, 2),
                    processed_width=w, processed_height=h, processed_bytes=ob)

        # Pass-through: nothing to fix and already a safe mode -> keep original
        # bytes verbatim (no lossy re-encode, no extra work).
        if not has_orientation and not needs_resize and img.mode in ("RGB", "L"):
            return image_bytes, mime_type, meta

        # Camera JPEGs that exceed the upload dimension are the C++ target.
        # Other formats retain the existing subprocess/Pillow behavior.
        cpp_eligible = needs_resize and img.format == "JPEG" and img.mode in ("RGB", "L")
        if cpp_eligible:
            native_result = _try_native_preprocess(image_bytes, max_dimension, quality)
        elif settings.NATIVE_IMAGE_PREPROCESSOR_PATH.strip():
            # Preserve the older subprocess helper's full format coverage.
            native_result = _try_native_preprocess(
                image_bytes, max_dimension, quality, use_library=False,
            )
        else:
            native_result = None
        if native_result:
            out, out_mime, out_size = native_result
            meta.update(
                was_resized=needs_resize,
                was_reencoded=True,
                preprocess_backend="native",
                processed_width=out_size[0],
                processed_height=out_size[1],
                processed_bytes=len(out),
            )
            return out, out_mime, meta

        if needs_resize and img.format == "JPEG":
            # JPEG decoders can discard DCT blocks while decoding.  For large
            # camera photos this avoids materializing the full-resolution
            # bitmap before the final resize; PNG/WebP do not offer an
            # equivalent safe decoder hint, so they follow the normal path.
            scale = max_dimension / max(w, h)
            img.draft(
                "RGB",
                (max(1, int(w * scale)), max(1, int(h * scale))),
            )

        img = ImageOps.exif_transpose(img)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")

        if needs_resize:
            # thumbnail() uses Pillow's integer pre-reduction before its final
            # LANCZOS pass.  It produces the same bounded aspect-preserving
            # result as resize(), but avoids applying expensive LANCZOS over
            # every source pixel for very large camera images.
            img.thumbnail(
                (max_dimension, max_dimension),
                Image.LANCZOS,
                reducing_gap=3.0,
            )
            meta["was_resized"] = True

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        out = buf.getvalue()
        meta["was_reencoded"] = True
        meta["preprocess_backend"] = "pillow"
        meta["processed_width"], meta["processed_height"] = img.size
        meta["processed_bytes"] = len(out)
        return out, "image/jpeg", meta
    except Exception as e:
        logger.warning("image preprocessing failed (%s), using original", type(e).__name__)
        return image_bytes, mime_type, meta


def preprocess_image(
    image_bytes: bytes,
    mime_type: str,
    max_dimension: int,
) -> tuple[bytes, str]:
    """Benchmark-compatible wrapper: EXIF/downscale/re-encode using configured JPEG quality."""
    out, mime, _ = _preprocess(
        image_bytes, mime_type, max_dimension, settings.PREPROCESS_JPEG_QUALITY
    )
    return out, mime


# ── Provider calls ──────────────────────────────────────────────────────────

async def _call_chat(
    messages: list[dict],
    model: str,
    timeout: float,
    temperature: float,
    max_tokens: int,
    json_mode: bool = False,
) -> tuple[str, dict]:
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}

    resp = await get_client().post(
        f"{settings.AI_VISION_BASE_URL}/chat/completions",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.AI_VISION_API_KEY}",
        },
        json=body,
        timeout=timeout,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"AI API error {resp.status_code}")

    data = resp.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "") or ""
    return content, (data.get("usage") or {})


async def _run_ocr(data_url: str) -> tuple[str, dict]:
    messages = [
        {"role": "system", "content": OCR_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Transcribe all readable text from this product image, exactly as shown."},
                {"type": "image_url", "image_url": {"url": data_url, "detail": "high"}},
            ],
        },
    ]
    return await _call_chat(
        messages, settings.AI_OCR_MODEL, settings.AI_OCR_TIMEOUT,
        temperature=0.0, max_tokens=4000, json_mode=False,
    )


async def _run_vision(data_url: str, ocr_text: str) -> tuple[str, dict]:
    has_readable_text = bool(ocr_text.strip())
    user_text = (
        "Product image OCR text (supplementary evidence only):\n"
        + (ocr_text.strip() or "(no readable text recognized)")
        + "\n\nUsing the ORIGINAL IMAGE as the primary evidence and the OCR text as "
        "supplementary evidence, extract only the product attributes you can confirm. "
        "Return null for any field you cannot confirm. "
        + ("Preserve the original language in all text fields; never translate text into English."
           if has_readable_text else
           "No readable text was recognized. For visually confirmed text fields, use Simplified Chinese; do not invent details.")
    )
    messages = [
        {"role": "system", "content": VISION_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_text},
                {"type": "image_url", "image_url": {"url": data_url, "detail": "high"}},
            ],
        },
    ]
    return await _call_chat(
        messages, settings.AI_VISION_MODEL, settings.AI_VISION_TIMEOUT,
        temperature=0.0, max_tokens=1200, json_mode=True,
    )


# ── Orchestration ───────────────────────────────────────────────────────────

async def recognize_product_image(image_bytes: bytes, mime_type: str) -> dict[str, Any]:
    """Preprocess -> OCR -> vision -> sanitize. Returns the 12 Product fields."""
    ocr_model = settings.AI_OCR_MODEL
    vision_model = settings.AI_VISION_MODEL
    if not (settings.AI_VISION_API_KEY and settings.AI_VISION_BASE_URL and ocr_model and vision_model):
        logger.error(
            "recognition not configured "
            "(AI_OCR_MODEL / AI_VISION_MODEL / AI_VISION_API_KEY / AI_VISION_BASE_URL)"
        )
        raise RuntimeError("recognition not configured")

    start = time.perf_counter()

    t0 = time.perf_counter()
    processed_bytes, processed_mime, pmeta = await asyncio.get_running_loop().run_in_executor(
        _IMAGE_PREPROCESS_EXECUTOR,
        partial(
            _preprocess,
            image_bytes,
            mime_type,
            settings.AI_MAX_IMAGE_DIMENSION,
            settings.PREPROCESS_JPEG_QUALITY,
        ),
    )
    preprocess_ms = int((time.perf_counter() - t0) * 1000)

    t0 = time.perf_counter()
    b64 = base64.b64encode(processed_bytes).decode("ascii")
    base64_ms = int((time.perf_counter() - t0) * 1000)
    data_url = f"data:{processed_mime};base64,{b64}"

    t0 = time.perf_counter()
    ocr_text, ocr_usage = await _run_ocr(data_url)
    ocr_ms = int((time.perf_counter() - t0) * 1000)

    t0 = time.perf_counter()
    vision_content, vision_usage = await _run_vision(data_url, ocr_text)
    vision_ms = int((time.perf_counter() - t0) * 1000)

    total_ms = int((time.perf_counter() - start) * 1000)

    ob = pmeta["original_bytes"]
    pb = pmeta["processed_bytes"]
    compression_ratio = round(pb / ob, 3) if ob else 0.0
    logger.info(
        "[PRODUCT_AI] original_width=%s original_height=%s original_bytes=%s "
        "processed_width=%s processed_height=%s processed_bytes=%s "
        "compression_ratio=%s image_megapixels=%s was_resized=%s was_reencoded=%s "
        "preprocess_backend=%s "
        "preprocess_ms=%s base64_ms=%s ocr_ms=%s vision_ms=%s total_ms=%s "
        "ocr_model=%s vision_model=%s ocr_in=%s ocr_out=%s vision_in=%s vision_out=%s",
        pmeta["original_width"], pmeta["original_height"], ob,
        pmeta["processed_width"], pmeta["processed_height"], pb,
        compression_ratio, pmeta["megapixels"], pmeta["was_resized"], pmeta["was_reencoded"],
        pmeta["preprocess_backend"],
        preprocess_ms, base64_ms, ocr_ms, vision_ms, total_ms,
        ocr_model, vision_model,
        ocr_usage.get("prompt_tokens", 0), ocr_usage.get("completion_tokens", 0),
        vision_usage.get("prompt_tokens", 0), vision_usage.get("completion_tokens", 0),
    )

    return sanitize_recognition(_parse_json(vision_content))

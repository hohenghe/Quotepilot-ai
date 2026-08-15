"""Vision: recognize product attributes from a product photo via a multimodal LLM.

This module never touches the database. It only:
  1. calls the OpenAI-compatible chat/completions API with an image,
  2. parses + sanitizes the model's JSON into user-editable Product fields.

The API key is read from settings (OPENAI_API_KEY) and never returned to callers.
"""
import base64
import json
import logging
import re
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

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

VISION_SYSTEM_PROMPT = """You are a product information extractor for an international trade platform. Analyze the provided product photo and extract only the product attributes that are clearly identifiable from the image.

Rules:
- Only return information you can actually confirm from the image.
- Return null for any field you cannot confirm. Never guess or fill in from general knowledge.
- Do not fabricate brand, model, dimensions, weight, or any value not visible.
- If readable text appears in the image (labels, spec sheets, packaging), you may extract it (name, technical specs, certifications like CE/RoHS, SKU).
- Numeric business fields (moq, unit_price, price_range_low, price_range_high, lead_time_days) may ONLY be filled when the image explicitly shows the value (e.g. "MOQ: 100 pcs", "$2.50 / piece"). Do NOT estimate pricing or MOQ from product appearance.
- If the image contains multiple products, focus on the main product; if you cannot determine a main product, return all fields as null.
- If the image is clearly not a product (a person, landscape, text document without a product), return all fields as null.
- Return ONLY valid JSON. No markdown, no code fences, no extra text.

Return JSON in exactly this shape:
{
  "name": "string|null",
  "sku": "string|null",
  "category": "one of led_lighting, electronics, machinery, textiles, furniture, packaging, auto_parts, hardware, other, or null",
  "description": "string|null",
  "technical_specs": "string|null",
  "certifications": "string|null",
  "moq": "number|null",
  "unit_price": "number|null",
  "price_range_low": "number|null",
  "price_range_high": "number|null",
  "pricing": "string|null",
  "lead_time_days": "number|null"
}
"""


def _vision_model() -> str:
    return settings.AI_VISION_MODEL


def _vision_api_key() -> str:
    return settings.AI_VISION_API_KEY


def _vision_base_url() -> str:
    return settings.AI_VISION_BASE_URL


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


def _clean_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float) and value.is_integer() and value >= 0:
        return int(value)
    return None


def _clean_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if value >= 0 else None
    return None


def _clean_category(value: Any) -> str | None:
    s = _clean_str(value, _LEN_SKU)
    if s is None:
        return None
    return s if s in ALLOWED_CATEGORIES else None


def _empty_fields() -> dict[str, Any]:
    return {k: None for k in _FIELD_KEYS}


def sanitize_recognition(parsed: Any) -> dict[str, Any]:
    """Whitelist + coerce model output into safe, user-editable Product fields.

    Only the 12 user-editable Product fields are kept. Internal fields (id,
    seller_id, user_id, timestamps, permissions, ...) are always dropped.
    """
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


async def recognize_product_image(image_bytes: bytes, mime_type: str) -> dict[str, Any]:
    """Send a single product image to the vision model and return sanitized fields."""
    model = _vision_model()
    api_key = _vision_api_key()
    base_url = _vision_base_url()
    if not (model and api_key and base_url):
        logger.error(
            "vision model not configured (AI_VISION_MODEL / AI_VISION_API_KEY / AI_VISION_BASE_URL)"
        )
        raise RuntimeError("vision model not configured")

    b64 = base64.b64encode(image_bytes).decode("ascii")

    body: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": VISION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Analyze this product photo and extract the product attributes.",
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{b64}",
                            "detail": "low",
                        },
                    },
                ],
            },
        ],
        "temperature": 0.1,
        "max_tokens": 600,
        "response_format": {"type": "json_object"},
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{base_url}/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            json=body,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"vision API error {resp.status_code}")

        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

    return sanitize_recognition(_parse_json(content))

"""Unit tests for vision sanitization + preprocessing + pipeline (no DB / no network).

Run:  python tests/test_vision_unit.py
"""
import os
import sys
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.vision import (
    sanitize_recognition,
    _parse_json,
    preprocess_image,
)
import app.services.vision as vision

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"  {'PASS' if cond else 'FAIL'}  {name} {detail}")


def test_sanitize():
    r = sanitize_recognition({
        "name": "LED Panel Light",
        "category": "led_lighting",
        "certifications": "CE, RoHS",
        "moq": 100,
        "unit_price": 12.5,
        "description": "60x60cm panel",
        "brand": "SHOULD BE DROPPED",
        "id": 999,
        "seller_id": 1,
        "owner_id": 2,
    })
    check("name kept", r["name"] == "LED Panel Light")
    check("category kept", r["category"] == "led_lighting")
    check("moq int", r["moq"] == 100)
    check("unit_price float", r["unit_price"] == 12.5)
    check("brand dropped", "brand" not in r)
    check("id dropped", "id" not in r)
    check("seller_id dropped", "seller_id" not in r)

    keys = {"name", "sku", "category", "description", "technical_specs",
            "certifications", "moq", "unit_price", "price_range_low",
            "price_range_high", "pricing", "lead_time_days"}
    check("exactly 12 whitelisted keys", set(r.keys()) == keys)

    check("invalid category null", sanitize_recognition({"category": "weapons"})["category"] is None)
    check("non-dict -> all null", all(v is None for v in sanitize_recognition("x").values()))
    check("bad moq null", sanitize_recognition({"moq": "abc"})["moq"] is None)
    check("negative price null", sanitize_recognition({"unit_price": -5})["unit_price"] is None)
    check("negative moq null", sanitize_recognition({"moq": -1})["moq"] is None)
    check("negative lead_time null", sanitize_recognition({"lead_time_days": -3})["lead_time_days"] is None)
    check("nested fields", sanitize_recognition({"fields": {"name": "N"}})["name"] == "N")


def test_parse():
    check("parse plain json", _parse_json('{"a": 1}') == {"a": 1})
    check("parse fenced json", _parse_json('```json\n{"a": 1}\n```') == {"a": 1})
    check("parse garbage -> {}", _parse_json("hello") == {})
    check("parse non-str -> {}", _parse_json(None) == {})


def test_preprocess():
    from io import BytesIO
    from PIL import Image

    # Large PNG -> downscaled JPEG
    img = Image.new("RGB", (3000, 2000), (255, 0, 0))
    buf = BytesIO()
    img.save(buf, format="PNG")
    out_bytes, out_mime = preprocess_image(buf.getvalue(), "image/png", 1024)
    check("preprocess -> jpeg", out_mime == "image/jpeg")
    out_img = Image.open(BytesIO(out_bytes))
    check("preprocess downscale <= max", max(out_img.size) <= 1024, str(out_img.size))

    # Small image -> not upscaled (kept small)
    small = Image.new("RGB", (200, 100), (0, 255, 0))
    sbuf = BytesIO()
    small.save(sbuf, format="PNG")
    out2, _ = preprocess_image(sbuf.getvalue(), "image/png", 2048)
    out_img2 = Image.open(BytesIO(out2))
    check("preprocess keeps small image", max(out_img2.size) <= 2048 and min(out_img2.size) >= 100, str(out_img2.size))

    # Garbage bytes -> fallback to original
    out3, mime3 = preprocess_image(b"\x00\x01\x02", "image/jpeg", 2048)
    check("preprocess fallback on garbage", out3 == b"\x00\x01\x02" and mime3 == "image/jpeg")


def test_pipeline():
    from app.core.config import settings

    settings.AI_VISION_API_KEY = "test-key"
    settings.AI_VISION_BASE_URL = "http://test/v1"
    settings.AI_OCR_MODEL = "ocr-model"
    settings.AI_VISION_MODEL = "vision-model"

    call_order = []

    async def fake_call_chat(messages, model, timeout, temperature, max_tokens, json_mode=False):
        call_order.append(model)
        if not json_mode:
            return "LED Panel 60x60cm\nCE RoHS\nMOQ: 100", {"prompt_tokens": 10, "completion_tokens": 5}
        return '{"name":"LED Panel Light","category":"led_lighting","moq":100,"certifications":"CE, RoHS"}', \
               {"prompt_tokens": 20, "completion_tokens": 8}

    vision._call_chat = fake_call_chat

    async def run():
        return await vision.recognize_product_image(b"not-an-image", "image/jpeg")

    result = asyncio.run(run())
    check("pipeline name", result["name"] == "LED Panel Light")
    check("pipeline category", result["category"] == "led_lighting")
    check("pipeline moq int", result["moq"] == 100)
    check("pipeline certs", result["certifications"] == "CE, RoHS")
    check("pipeline order ocr->vision", call_order == ["ocr-model", "vision-model"], str(call_order))


if __name__ == "__main__":
    test_sanitize()
    test_parse()
    test_preprocess()
    test_pipeline()
    passed = sum(1 for _, ok in results if ok)
    failed = sum(1 for _, ok in results if not ok)
    print(f"\n{passed} passed, {failed} failed, {len(results)} total")
    if failed:
        sys.exit(1)

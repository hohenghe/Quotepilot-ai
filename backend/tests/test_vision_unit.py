"""Unit tests for vision sanitization (no DB / no network / no API key).

Run:  python tests/test_vision_unit.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.vision import sanitize_recognition, _parse_json

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"  {'PASS' if cond else 'FAIL'}  {name} {detail}")


def test_sanitize():
    # Valid result (flat fields)
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
    check("owner_id dropped", "owner_id" not in r)

    # All 12 keys present, null by default
    keys = {"name", "sku", "category", "description", "technical_specs",
            "certifications", "moq", "unit_price", "price_range_low",
            "price_range_high", "pricing", "lead_time_days"}
    check("exactly 12 whitelisted keys", set(r.keys()) == keys, str(sorted(r.keys())))

    # Invalid category -> null
    r = sanitize_recognition({"category": "weapons"})
    check("invalid category null", r["category"] is None)

    # Non-dict input -> all null
    r = sanitize_recognition("not json")
    check("non-dict -> all null", all(v is None for v in r.values()))

    r = sanitize_recognition(None)
    check("None -> all null", all(v is None for v in r.values()))

    # Type coercion: bad types -> null
    r = sanitize_recognition({"moq": "abc", "unit_price": -5, "name": 123})
    check("bad moq null", r["moq"] is None)
    check("negative price null", r["unit_price"] is None)
    check("non-str name null", r["name"] is None)

    # MOQ/price/lead_time must be >= 0
    r = sanitize_recognition({"moq": -1, "lead_time_days": -3, "price_range_low": -0.1})
    check("negative moq null", r["moq"] is None)
    check("negative lead_time null", r["lead_time_days"] is None)
    check("negative price_range null", r["price_range_low"] is None)

    # nested "fields" object tolerated
    r = sanitize_recognition({"fields": {"name": "Nested", "category": "electronics"}})
    check("nested fields name", r["name"] == "Nested")
    check("nested fields category", r["category"] == "electronics")

    # string length truncation
    r = sanitize_recognition({"name": "a" * 1000})
    check("name truncated to 300", len(r["name"]) == 300)


def test_parse():
    check("parse plain json", _parse_json('{"a": 1}') == {"a": 1})
    check("parse fenced json", _parse_json('```json\n{"a": 1}\n```') == {"a": 1})
    check("parse garbage -> {}", _parse_json("hello world") == {})
    check("parse non-str -> {}", _parse_json(None) == {})


if __name__ == "__main__":
    test_sanitize()
    test_parse()
    passed = sum(1 for _, ok in results if ok)
    failed = sum(1 for _, ok in results if not ok)
    print(f"\n{passed} passed, {failed} failed, {len(results)} total")
    if failed:
        sys.exit(1)

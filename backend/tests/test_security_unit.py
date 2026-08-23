"""Security unit tests (no DB / no network).

Run:  python tests/test_security_unit.py

Covers: JWT fail-closed validation, raw_message length cap, magic-byte
verification, production seed gating.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"  {'PASS' if cond else 'FAIL'}  {name} {detail}")


def test_jwt_secret_fail_closed():
    """P0-1: production must refuse to boot with the default / short JWT secret."""
    from pydantic import ValidationError
    from app.core.config import Settings, _DEV_JWT_SECRET

    # Default secret in production → must raise
    try:
        Settings(ENV="production", JWT_SECRET_KEY=_DEV_JWT_SECRET)
        check("prod default secret rejected", False, "did not raise")
    except (ValidationError, ValueError):
        check("prod default secret rejected", True)

    # Empty secret in production → must raise
    try:
        Settings(ENV="production", JWT_SECRET_KEY="")
        check("prod empty secret rejected", False, "did not raise")
    except (ValidationError, ValueError):
        check("prod empty secret rejected", True)

    # Short secret in production → must raise
    try:
        Settings(ENV="production", JWT_SECRET_KEY="a" * 31)
        check("prod short secret rejected", False, "did not raise")
    except (ValidationError, ValueError):
        check("prod short secret rejected", True)

    # Valid 32-byte secret in production → must NOT raise
    try:
        s = Settings(ENV="production", JWT_SECRET_KEY="a" * 32)
        check("prod valid secret accepted", s.ENV == "production")
    except (ValidationError, ValueError) as e:
        check("prod valid secret accepted", False, str(e))

    # Dev mode with default secret → must NOT raise (dev is allowed)
    try:
        s = Settings(ENV="development", JWT_SECRET_KEY=_DEV_JWT_SECRET)
        check("dev default secret allowed", s.ENV == "development")
    except (ValidationError, ValueError) as e:
        check("dev default secret allowed", False, str(e))


def test_raw_message_length_cap():
    """P0-3: raw_message > 4000 chars must be rejected by schema validation."""
    from pydantic import ValidationError
    from app.schemas.inquiry import InquiryCreate

    # Exactly 4000 → OK
    try:
        InquiryCreate(raw_message="x" * 4000)
        check("raw_message 4000 chars accepted", True)
    except ValidationError as e:
        check("raw_message 4000 chars accepted", False, str(e))

    # 4001 → rejected
    try:
        InquiryCreate(raw_message="x" * 4001)
        check("raw_message 4001 chars rejected", False, "did not raise")
    except ValidationError:
        check("raw_message 4001 chars rejected", True)

    # Empty → rejected (required field)
    try:
        InquiryCreate(raw_message="")
        check("raw_message empty rejected", False, "did not raise")
    except ValidationError:
        check("raw_message empty rejected", True)


def test_magic_bytes_products():
    """P1-17: product upload magic-byte validation rejects mismatched content."""
    from app.api.products import _validate_magic

    # PDF with %PDF magic → OK
    check("pdf valid magic", not _should_raise(lambda: _validate_magic(".pdf", b"%PDF-1.4...")))

    # Non-PDF content with .pdf extension → reject
    check("pdf invalid magic", _should_raise(lambda: _validate_magic(".pdf", b"NOT A PDF")))

    # XLSX (ZIP) with PK magic → OK
    check("xlsx valid magic", not _should_raise(lambda: _validate_magic(".xlsx", b"PK\x03\x04...")))

    # Non-ZIP content with .xlsx extension → reject
    check("xlsx invalid magic", _should_raise(lambda: _validate_magic(".xlsx", b"NOT A ZIP")))

    # CSV → no magic check (always OK)
    check("csv no magic check", not _should_raise(lambda: _validate_magic(".csv", b"anything")))


def test_magic_bytes_images():
    """P1-17: image upload magic-byte validation rejects mismatched content."""
    from app.api.files import _verify_image_magic

    # JPEG with \xff\xd8\xff → valid
    check("jpeg valid magic", _verify_image_magic(b"\xff\xd8\xff\xe0", "image/jpeg"))

    # PNG with \x89PNG → valid
    check("png valid magic", _verify_image_magic(b"\x89PNG\r\n\x1a\n", "image/png"))

    # GIF with GIF89a → valid
    check("gif valid magic", _verify_image_magic(b"GIF89a", "image/gif"))

    # WebP with RIFF → valid
    check("webp valid magic", _verify_image_magic(b"RIFF....", "image/webp"))

    # HTML content declared as JPEG → invalid
    check("html as jpeg rejected", not _verify_image_magic(b"<html>", "image/jpeg"))

    # Unknown content-type → invalid
    check("unknown content-type rejected", not _verify_image_magic(b"\xff\xd8\xff", "application/octet-stream"))


def test_production_seed_gating():
    """P0-2: test accounts must never be created in production."""
    from seed_admin import _should_create_test_accounts
    from app.core.config import settings

    # Save and override
    original_env = settings.ENV
    try:
        settings.ENV = "production"
        check("prod no test accounts", _should_create_test_accounts() is False)

        settings.ENV = "development"
        settings.CREATE_TEST_ACCOUNTS = "false"
        check("dev no opt-in no test accounts", _should_create_test_accounts() is False)

        settings.CREATE_TEST_ACCOUNTS = "true"
        check("dev opt-in creates test accounts", _should_create_test_accounts() is True)
    finally:
        settings.ENV = original_env


def _should_raise(fn) -> bool:
    """Return True if calling fn() raises HTTPException, else False."""
    from fastapi import HTTPException
    try:
        fn()
        return False
    except HTTPException:
        return True


def main():
    print("=== JWT fail-closed (P0-1) ===")
    test_jwt_secret_fail_closed()
    print("\n=== raw_message length cap (P0-3) ===")
    test_raw_message_length_cap()
    print("\n=== Product upload magic bytes (P1-17) ===")
    test_magic_bytes_products()
    print("\n=== Image upload magic bytes (P1-17) ===")
    test_magic_bytes_images()
    print("\n=== Production seed gating (P0-2) ===")
    test_production_seed_gating()

    passed = sum(1 for _, ok in results if ok)
    failed = sum(1 for _, ok in results if not ok)
    print(f"\n{passed} passed, {failed} failed, {len(results)} total")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()

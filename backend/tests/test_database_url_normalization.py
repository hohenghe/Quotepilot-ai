"""Unit tests for PostgreSQL URL normalization (no database required)."""
from urllib.parse import parse_qsl, urlsplit

from app.core.config import Settings


def test_postgresql_url_converts_driver_and_sslmode():
    settings = Settings(
        DATABASE_URL="postgresql://user:password@host:5432/db?sslmode=require"
    )
    assert settings.DATABASE_URL == (
        "postgresql+asyncpg://user:password@host:5432/db?ssl=require"
    )


def test_asyncpg_url_converts_sslmode():
    settings = Settings(
        DATABASE_URL="postgresql+asyncpg://user:password@host:5432/db?sslmode=require"
    )
    assert settings.DATABASE_URL == (
        "postgresql+asyncpg://user:password@host:5432/db?ssl=require"
    )


def test_url_without_sslmode_does_not_add_ssl():
    settings = Settings(DATABASE_URL="postgresql://user:password@host:5432/db")
    assert settings.DATABASE_URL == "postgresql+asyncpg://user:password@host:5432/db"


def test_url_preserves_other_query_parameters_and_encoded_password():
    original = (
        "postgresql://user:pa%40ss%3Aword@host:5432/db?"
        "application_name=quotepilot&sslmode=verify-full&connect_timeout=5"
    )
    settings = Settings(DATABASE_URL=original)
    parsed = urlsplit(settings.DATABASE_URL)

    assert parsed.scheme == "postgresql+asyncpg"
    assert parsed.netloc == "user:pa%40ss%3Aword@host:5432"
    assert parse_qsl(parsed.query, keep_blank_values=True) == [
        ("application_name", "quotepilot"),
        ("ssl", "verify-full"),
        ("connect_timeout", "5"),
    ]

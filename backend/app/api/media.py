"""Validation for image URLs stored by profile, product, and review APIs."""

from fastapi import HTTPException, Request

from app.core.config import is_production
from app.services.storage import (
    R2ConfigurationError,
    validate_media_reference,
    validate_media_references,
)


def media_url(request: Request, kind: str, name: str) -> str:
    url = request.url_for("get_r2_media", kind=kind, name=name)
    return str(url.replace(scheme="https") if is_production() else url)


def _base_url(request: Request) -> str:
    base = request.base_url
    return str(base.replace(scheme="https") if is_production() else base)


def require_media_url(
    value: str | None, kind: str, *, request: Request, existing: str | None = None,
) -> str | None:
    try:
        return validate_media_reference(value, kind, base_url=_base_url(request), existing=existing)
    except R2ConfigurationError as exc:
        raise HTTPException(status_code=503, detail="Image storage is not configured") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def require_media_urls(
    values: list[str], kind: str, *, request: Request, existing: list[str] | None = None,
) -> list[str]:
    try:
        return validate_media_references(values, kind, base_url=_base_url(request), existing=existing)
    except R2ConfigurationError as exc:
        raise HTTPException(status_code=503, detail="Image storage is not configured") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

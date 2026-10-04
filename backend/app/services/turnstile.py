"""Validate browser challenge tokens with Cloudflare before costly work."""
import logging
from urllib.parse import urlsplit

from fastapi import HTTPException, Request

from app.core.config import get_cors_origins, settings
from app.core.http_clients import get_http_client

logger = logging.getLogger(__name__)
SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
_TEST_SECRETS = {
    "1x0000000000000000000000000000000AA",
    "2x0000000000000000000000000000000AA",
    "3x0000000000000000000000000000000AA",
}


def _allowed_hostnames() -> set[str]:
    configured = settings.TURNSTILE_ALLOWED_HOSTNAMES.strip()
    if configured:
        return {name.strip().lower() for name in configured.split(",") if name.strip()}
    return {urlsplit(origin).hostname.lower() for origin in get_cors_origins()
            if urlsplit(origin).hostname}


def _browser_origin(request: Request | None) -> bool:
    if request is None:
        return False
    origin = request.headers.get("origin", "").rstrip("/")
    return origin in get_cors_origins()


async def verify_turnstile(request: Request | None, token: str | None, action: str,
                           *, require_for_all: bool = False) -> None:
    """Enforce on web origins or every caller of a web-only API.

    Shared auth endpoints keep supporting the WeChat mini program, which has
    no browser Origin header. Its existing rate limits remain in force.
    """
    if not settings.TURNSTILE_SECRET_KEY:
        return
    if not token and not (require_for_all or _browser_origin(request)):
        return
    if settings.ENV == "production" and settings.TURNSTILE_SECRET_KEY in _TEST_SECRETS:
        logger.error("Turnstile test secret configured in production")
        raise HTTPException(status_code=503, detail="Human verification is misconfigured.")
    if not token:
        raise HTTPException(status_code=403, detail="Human verification required.")
    try:
        response = await get_http_client().post(
            SITEVERIFY_URL,
            json={"secret": settings.TURNSTILE_SECRET_KEY, "response": token},
            timeout=5.0,
        )
        response.raise_for_status()
        result = response.json()
    except Exception:
        logger.warning("Turnstile Siteverify unavailable", exc_info=True)
        raise HTTPException(status_code=503, detail="Human verification is temporarily unavailable.")
    if (isinstance(result, dict) and result.get("success") is True
            and settings.ENV != "production"
            and settings.TURNSTILE_SECRET_KEY in _TEST_SECRETS
            and isinstance(result.get("metadata"), dict)
            and result["metadata"].get("result_with_testing_key") is True):
        return
    if (not isinstance(result, dict) or result.get("success") is not True
            or result.get("action") != action
            or not isinstance(result.get("hostname"), str)
            or result["hostname"].lower() not in _allowed_hostnames()):
        raise HTTPException(status_code=403, detail="Human verification failed. Please try again.")

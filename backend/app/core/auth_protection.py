"""Bounded, process-local guards for expensive authentication requests."""
import hashlib
import hmac
import time
import asyncio

from app.core.config import settings
from app.core.ratelimit import rate_exceeded

_failures: dict[str, tuple[int, float]] = {}
_FAILURE_WINDOW = 300
_FAILURE_LIMIT = 10
_MAX_FAILURE_KEYS = 10_000
_password_slots: asyncio.Semaphore | None = None


async def run_password_operation(function, *args):
    """Keep Argon2 work off the event loop and bound concurrent memory use."""
    global _password_slots
    if _password_slots is None:
        _password_slots = asyncio.Semaphore(4)
    async with _password_slots:
        return await asyncio.to_thread(function, *args)


def _identifier_key(identifier: str) -> str:
    normalized = identifier.strip().lower() if "@" in identifier else identifier.strip()
    return hmac.new(settings.JWT_SECRET_KEY.encode(), normalized.encode(), hashlib.sha256).hexdigest()


def login_locked(identifier: str) -> bool:
    key = _identifier_key(identifier)
    count, expires = _failures.get(key, (0, 0.0))
    if time.monotonic() >= expires:
        _failures.pop(key, None)
        return False
    return count >= _FAILURE_LIMIT


def record_login_failure(identifier: str) -> None:
    key = _identifier_key(identifier)
    now = time.monotonic()
    count, expires = _failures.get(key, (0, 0.0))
    if now >= expires:
        count, expires = 0, now + _FAILURE_WINDOW
    if len(_failures) >= _MAX_FAILURE_KEYS and key not in _failures:
        _failures.pop(next(iter(_failures)))
    _failures[key] = (count + 1, expires)


def clear_login_failures(identifier: str) -> None:
    _failures.pop(_identifier_key(identifier), None)


def auth_request_limited(path: str, client_ip: str) -> bool:
    """Reject excess requests before parsing bodies or opening a DB session."""
    if path in {"/api/auth/login", "/api/auth/wechat-bind"}:
        return rate_exceeded(f"auth-login:{client_ip}", 20)
    if path in {"/api/auth/register", "/api/auth/wechat-register"}:
        return rate_exceeded(f"auth-register:{client_ip}", 10)
    if path in {"/api/auth/forgot-password", "/api/auth/resend-verification", "/api/auth/reset-password"}:
        return rate_exceeded(f"auth-email:{client_ip}", 10)
    if path == "/api/auth/verify-email":
        return rate_exceeded(f"auth-verify:{client_ip}", 20)
    if path in {"/api/auth/wechat-login", "/api/auth/wechat-session", "/api/auth/wechat-phone"}:
        return rate_exceeded(f"auth-wechat:{client_ip}", 30)
    return False

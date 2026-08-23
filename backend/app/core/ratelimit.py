"""Lightweight in-memory rate limiting for the anonymous /analyze endpoint.

Designed for a single-worker Railway deployment. Keyed by client IP for guests
and by user id for authenticated callers. A global concurrency semaphore caps
in-flight /analyze requests to prevent DB-connection-pool exhaustion under
flood (the primary DoS vector for this endpoint).
"""
import asyncio
import time
from collections import defaultdict, deque
from typing import Optional

import logging

logger = logging.getLogger(__name__)

# Sliding-window counters: key -> deque of monotonic timestamps.
_windows: dict[str, deque] = defaultdict(deque)

_WINDOW_SECONDS = 60

# Lazy global semaphore (created on first use inside the running event loop).
_analyze_semaphore: Optional[asyncio.Semaphore] = None


def get_client_ip(request) -> str:
    """Extract the real client IP, accounting for reverse proxies (Railway /
    Cloudflare). Uses the leftmost X-Forwarded-For entry (the original client
    per the de-facto spec). Falls back to the direct TCP peer.

    Note: a determined attacker can rotate/spoof X-Forwarded-For to bypass
    per-IP limits. This is mitigated by the global concurrency cap, which is
    IP-independent. The per-IP limit primarily stops a single script on a
    single connection from flooding."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        # Leftmost is the original client; rightmost is the closest proxy.
        first = xff.split(",")[0].strip()
        if first:
            return first
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip.strip()
    return request.client.host if request.client else "unknown"


def rate_exceeded(key: str, limit: int) -> bool:
    """Return True if the key has exceeded `limit` requests in the sliding window."""
    now = time.monotonic()
    dq = _windows[key]
    while dq and now - dq[0] > _WINDOW_SECONDS:
        dq.popleft()
    if len(dq) >= limit:
        return True
    dq.append(now)
    return False


def get_analyze_semaphore() -> asyncio.Semaphore:
    """Global concurrency cap for /analyze (IP-independent DoS backstop)."""
    global _analyze_semaphore
    if _analyze_semaphore is None:
        from app.core.config import settings
        _analyze_semaphore = asyncio.Semaphore(settings.ANALYZE_MAX_CONCURRENCY)
    return _analyze_semaphore

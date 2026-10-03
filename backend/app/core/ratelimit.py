"""Lightweight in-memory rate limiting for the anonymous /analyze endpoint.

Designed for a single-worker Railway deployment. Keyed by client IP for guests
and by user id for authenticated callers. A global concurrency semaphore caps
in-flight /analyze requests to prevent DB-connection-pool exhaustion under
flood (the primary DoS vector for this endpoint).
"""
import asyncio
import time
import ipaddress
from collections import deque
from typing import Optional

import logging

logger = logging.getLogger(__name__)

# Sliding-window counters: key -> deque of monotonic timestamps.
_windows: dict[str, deque] = {}

_WINDOW_SECONDS = 60
_MAX_WINDOW_KEYS = 10_000
_last_sweep = 0.0

# Lazy global semaphore (created on first use inside the running event loop).
_analyze_semaphore: Optional[asyncio.Semaphore] = None


def get_client_ip(request) -> str:
    """Use forwarding headers only when the immediate peer is trusted."""
    from app.core.config import settings

    peer = request.client.host if request.client else "unknown"
    try:
        peer_ip = ipaddress.ip_address(peer)
    except ValueError:
        return peer
    networks = []
    for cidr in settings.TRUSTED_PROXY_CIDRS.split(","):
        if cidr.strip():
            networks.append(ipaddress.ip_network(cidr.strip(), strict=False))
    if not any(peer_ip in network for network in networks):
        return peer
    # Walk from the trusted peer towards the client; choose the first
    # untrusted address so user-supplied XFF prefixes cannot rotate keys.
    xff = request.headers.get("x-forwarded-for", "")
    for value in reversed(xff.split(",")):
        try:
            candidate = ipaddress.ip_address(value.strip())
        except ValueError:
            continue
        if not any(candidate in network for network in networks):
            return str(candidate)
    return peer


def rate_exceeded(key: str, limit: int) -> bool:
    """Return True if the key has exceeded `limit` requests in the sliding window."""
    global _last_sweep
    now = time.monotonic()
    if now - _last_sweep >= _WINDOW_SECONDS:
        for stale_key, timestamps in list(_windows.items()):
            if not timestamps or now - timestamps[-1] > _WINDOW_SECONDS:
                del _windows[stale_key]
        _last_sweep = now

    dq = _windows.get(key)
    if dq is None:
        if len(_windows) >= _MAX_WINDOW_KEYS:
            _windows.pop(next(iter(_windows)))
        dq = _windows[key] = deque()
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

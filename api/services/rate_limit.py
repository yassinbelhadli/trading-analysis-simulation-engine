"""In-memory fixed-window rate limiter for auth endpoints.

Single-process (uvicorn) deployment assumed. For multi-worker deployments,
move the counters to Redis or the DB. Never trust client IPs blindly behind a
proxy — a production deployment should read X-Forwarded-For only when the
proxy is trusted.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Dict, Tuple

from fastapi import Depends, HTTPException, Request

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_hits: Dict[Tuple[str, str], Tuple[int, float]] = {}


def _client_key(request: Request) -> str:
    ip = request.client.host if request.client else "unknown"
    return ip


def rate_limit(limit: int, window_seconds: int) -> Callable:
    """Dependency factory: allow `limit` requests per `window_seconds` per IP."""

    def dependency(request: Request) -> None:
        key = (_client_key(request), request.url.path)
        now = time.monotonic()
        with _lock:
            count, window_start = _hits.get(key, (0, now))
            if now - window_start >= window_seconds:
                count, window_start = 0, now
            if count >= limit:
                retry_after = int(window_seconds - (now - window_start)) + 1
                raise HTTPException(
                    status_code=429,
                    detail="Too many attempts. Please try again later.",
                    headers={"Retry-After": str(retry_after)},
                )
            _hits[key] = (count + 1, window_start)
            _trim(now)

    return dependency


def _trim(now: float, max_entries: int = 10000) -> None:
    """Remove expired entries; called under lock."""
    if len(_hits) <= max_entries:
        return
    expired = [k for k, (_, start) in _hits.items() if now - start > 3600]
    for k in expired:
        _hits.pop(k, None)


def clear_all() -> None:
    """Testing helper."""
    with _lock:
        _hits.clear()

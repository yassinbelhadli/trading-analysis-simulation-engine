"""Signed URLs for trade screenshots.

Screenshots are served from <img> tags, which cannot send Authorization
headers, so we issue short-lived HMAC-signed URLs from the snapshot endpoint.
The signature binds the exact file path + expiry to JWT_SECRET.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time

from urllib.parse import quote

SECRET = os.getenv("JWT_SECRET", "")
# Never allow unsigned access even if JWT_SECRET is unset (fail closed).
SIGN_TTL_SECONDS = int(os.getenv("SCREENSHOT_URL_TTL_SECONDS", "600"))


def _mac(message: str) -> str:
    return hmac.new(SECRET.encode(), message.encode(), hashlib.sha256).hexdigest()


def sign_screenshot_url(trade_id: str, filename: str) -> str:
    """Return an absolute API path with a short-lived signature."""
    exp = int(time.time()) + SIGN_TTL_SECONDS
    message = f"{trade_id}/{filename}:{exp}"
    sig = _mac(message)
    return f"/api/screenshots/{trade_id}/{quote(filename)}?exp={exp}&sig={sig}"


def verify_screenshot_signature(trade_id: str, filename: str, exp: str, sig: str) -> bool:
    if not SECRET:
        return False
    try:
        exp_i = int(exp)
    except (TypeError, ValueError):
        return False
    if exp_i < int(time.time()):
        return False
    expected = _mac(f"{trade_id}/{filename}:{exp_i}")
    return hmac.compare_digest(expected, sig)

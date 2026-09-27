"""TOTP (Time-based One-Time Password) helpers for 2FA.

Backed by ``cryptography``'s TOTP implementation (SHA1, 6 digits, 30s period)
which is compatible with Google Authenticator and similar apps.
"""
from __future__ import annotations

import base64
import os
import time
from typing import Optional
from urllib.parse import quote

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.twofactor import InvalidToken
from cryptography.hazmat.primitives.twofactor.totp import TOTP

ALGORITHM = hashes.SHA1()
DIGITS = 6
PERIOD = 30
ISSUER = "ICT EA Pro"


def generate_totp_secret() -> str:
    """Generate a base32 TOTP secret (20 random bytes)."""
    raw = os.urandom(20)
    return base64.b32encode(raw).decode("ascii").rstrip("=")


def build_otpauth_uri(secret: str, account: str) -> str:
    """otpauth:// URI for QR provisioning (works with Authenticator apps)."""
    label = quote(f"{ISSUER}:{account}", safe="")
    params = (
        f"secret={secret}&issuer={quote(ISSUER)}"
        f"&algorithm=SHA1&digits={DIGITS}&period={PERIOD}"
    )
    return f"otpauth://totp/{label}?{params}"


def _load_totp(secret: str) -> Optional[TOTP]:
    padded = secret.strip().upper()
    padded = padded + "=" * ((8 - len(padded) % 8) % 8)
    try:
        key = base64.b32decode(padded)
    except Exception:
        return None
    return TOTP(key, DIGITS, ALGORITHM, PERIOD)


def verify_totp(secret: str, code: str) -> bool:
    """Verify a 6-digit code allowing a skew of one period (±30s)."""
    code = (code or "").strip()
    if not code or not code.isdigit():
        return False
    totp = _load_totp(secret)
    if totp is None:
        return False
    for offset in (0, -1, 1):
        try:
            totp.verify(str(code).encode("ascii"), time.time() + offset * PERIOD)
            return True
        except InvalidToken:
            continue
    return False

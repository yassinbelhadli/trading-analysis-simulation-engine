from __future__ import annotations

import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt

logger = logging.getLogger(__name__)

SECRET_KEY = os.getenv("JWT_SECRET", "")
if not SECRET_KEY:
    raise RuntimeError("JWT_SECRET must be set in config/.env (do not reuse ENCRYPTION_KEY)")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_EXPIRE_DAYS", "30"))
SESSION_EXPIRE_DAYS = int(os.getenv("JWT_SESSION_EXPIRE_DAYS", "1"))
TWO_FA_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_2FA_EXPIRE_MINUTES", "5"))


def create_token(user_id: str, token_type: str, expire: datetime, role: Optional[str] = None) -> str:
    payload = {"sub": user_id, "exp": expire, "type": token_type}
    if role:
        payload["role"] = role
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(user_id: str, role: Optional[str] = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return create_token(user_id, "access", expire, role)


def create_2fa_token(user_id: str, role: Optional[str] = None) -> str:
    """Short-lived token proving step-1 (password) passed, awaiting a TOTP code."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=TWO_FA_TOKEN_EXPIRE_MINUTES)
    return create_token(user_id, "2fa", expire, role)


def create_refresh_token(user_id: str, days: Optional[int] = None) -> tuple[str, str, datetime]:
    days = days if days and days > 0 else REFRESH_TOKEN_EXPIRE_DAYS
    expire = datetime.now(timezone.utc) + timedelta(days=days)
    raw = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    return raw, token_hash, expire


def decode_token(token: str, expected_type: str = "access") -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if payload.get("type") != expected_type:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Invalid token type")
    return payload


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()

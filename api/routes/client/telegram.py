"""Client Telegram integration — OIDC Authorization Code + PKCE flow.

Connect flow (secure — Telegram OIDC):
  1. Dashboard calls GET /login -> backend generates state + PKCE verifier,
     stores them server-side, returns Telegram authorization URL.
  2. Browser redirects to Telegram's authorization page.
  3. User approves; Telegram redirects back with ?code=...&state=...
  4. Next.js API route forwards code+state to POST /callback-exchange.
  5. Backend exchanges code for tokens server-side, verifies ID token
     (RS256 signature, issuer, audience, expiration via Telegram JWKS),
     extracts Telegram user ID, links account.
  6. Redirect to /dashboard/telegram?telegram=connected.

Security properties:
  - State prevents CSRF.
  - PKCE S256 prevents authorization code interception.
  - ID token is verified server-side via Telegram JWKS (RS256).
  - Browser-supplied telegram_id is NEVER trusted — only the verified
    ID token proves ownership.
  - Unique constraint on users.telegram_id prevents one TG account -> 2 clients.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import secrets
import time
from typing import Any

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import get_session
from database.models import User
from security.audit import log_event
from security.auth import get_current_user
from api.services.notifications.preferences import (
    NOTIF_KEYS,
    get_user_notifications,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/client/telegram", tags=["client-telegram"])

BOT_USERNAME: str = os.getenv("TELEGRAM_BOT_USERNAME", "ict_funded_pro_ea_bot")
BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
CLIENT_ID: str = os.getenv("TELEGRAM_CLIENT_ID", "")
CLIENT_SECRET: str = os.getenv("TELEGRAM_CLIENT_SECRET", "")
REDIRECT_URI: str = os.getenv("TELEGRAM_REDIRECT_URI", "")
LANGUAGES = {"EN", "AR", "FR", "ES"}

# OIDC endpoints (Telegram official)
_TELEGRAM_AUTH_URL = "https://oauth.telegram.org/auth"
_TELEGRAM_TOKEN_URL = "https://oauth.telegram.org/token"
_TELEGRAM_JWKS_URL = "https://oauth.telegram.org/.well-known/jwks.json"
_TELEGRAM_ISSUER = "https://oauth.telegram.org"

# OIDC scopes: openid (required), profile (name/username), bot_access (bot can msg)
_OIDC_SCOPES = "openid profile telegram:bot_access"


# ---------------------------------------------------------------------------
# In-memory state store for pending OIDC flows
# ---------------------------------------------------------------------------
_oauth_states: dict[str, dict[str, Any]] = {}
_OAUTH_STATE_TTL = 300  # 5 minutes


def _store_oauth_state(state: str, code_verifier: str, user_id: str) -> None:
    """Store state -> {code_verifier, user_id, created_at} with expiry cleanup."""
    _oauth_states[state] = {
        "code_verifier": code_verifier,
        "user_id": user_id,
        "created_at": time.time(),
    }
    # Cleanup expired entries
    now = time.time()
    expired = [k for k, v in _oauth_states.items() if now - v["created_at"] > _OAUTH_STATE_TTL]
    for k in expired:
        del _oauth_states[k]


def _consume_oauth_state(state: str) -> dict[str, Any] | None:
    """Retrieve and consume (one-time use) an OAuth state. Returns None if invalid/expired."""
    entry = _oauth_states.pop(state, None)
    if entry and time.time() - entry["created_at"] <= _OAUTH_STATE_TTL:
        return entry
    return None


# ---------------------------------------------------------------------------
# JWKS cache
# ---------------------------------------------------------------------------
_jwks_cache: dict | None = None
_jwks_cache_time: float = 0
_JWKS_CACHE_TTL = 3600  # 1 hour


async def _fetch_jwks() -> dict:
    """Fetch Telegram's JWKS keys with caching."""
    global _jwks_cache, _jwks_cache_time
    now = time.time()
    if _jwks_cache and now - _jwks_cache_time < _JWKS_CACHE_TTL:
        return _jwks_cache
    async with httpx.AsyncClient() as client:
        resp = await client.get(_TELEGRAM_JWKS_URL, timeout=10)
        resp.raise_for_status()
        _jwks_cache = resp.json()
        _jwks_cache_time = now
    return _jwks_cache


def _validate_id_token(id_token: str) -> dict:
    """Validate a Telegram OIDC ID token. Returns decoded claims.

    Validates:
      - RS256 signature via Telegram JWKS
      - Issuer = https://oauth.telegram.org
      - Audience = CLIENT_ID (bot numeric ID)
      - Expiration
    """
    # Decode header to find kid and algorithm
    unverified_header = jwt.get_unverified_header(id_token)
    kid = unverified_header.get("kid")
    alg = unverified_header.get("alg", "RS256")

    if alg not in ("RS256", "ES256"):
        raise ValueError(f"Unsupported JWT algorithm: {alg}")

    # Fetch JWKS (synchronous http for simplicity in JWT verify path)
    jwks_resp = httpx.get(_TELEGRAM_JWKS_URL, timeout=10)
    jwks_resp.raise_for_status()
    jwks = jwks_resp.json()

    # Find matching key
    rsa_key = None
    for k in jwks.get("keys", []):
        if k.get("kid") == kid:
            rsa_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(k))
            break

    if not rsa_key:
        raise ValueError(f"JWKS key not found for kid={kid}")

    # Decode + verify signature, issuer, audience, expiration
    claims = jwt.decode(
        id_token,
        rsa_key,
        algorithms=["RS256"],
        audience=CLIENT_ID,
        issuer=_TELEGRAM_ISSUER,
        options={"require": ["exp", "iat", "iss", "aud", "sub"]},
    )
    return claims


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _notifications(user) -> dict:
    return get_user_notifications(user)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("")
async def client_telegram_status(
    current_user=Depends(get_current_user),
):
    """Telegram connection status + notification preferences."""
    bot_id = int(BOT_TOKEN.split(":")[0]) if BOT_TOKEN else 0
    return {
        "connected": current_user.telegram_id is not None,
        "bot_username": BOT_USERNAME,
        "bot_id": bot_id,
        "chat_id": current_user.telegram_id,
        "telegram_username": current_user.telegram_username,
        "language": current_user.language or "EN",
        "bot_link": f"https://t.me/{BOT_USERNAME}",
        "notifications": _notifications(current_user),
    }


@router.get("/login")
async def client_telegram_login(
    current_user=Depends(get_current_user),
):
    """Generate Telegram OIDC authorization URL with PKCE.

    Returns {url: "..."} — the frontend redirects the browser to this URL.
    """
    if not CLIENT_ID or not CLIENT_SECRET:
        raise HTTPException(
            status_code=500,
            detail="Telegram OIDC is not configured (missing CLIENT_ID or CLIENT_SECRET)",
        )
    if not REDIRECT_URI:
        raise HTTPException(
            status_code=500,
            detail="Telegram OIDC redirect URI is not configured",
        )

    # Generate state + PKCE
    state = secrets.token_urlsafe(32)
    code_verifier = secrets.token_urlsafe(64)  # 43-128 chars, URL-safe

    # Store in server-side memory (state -> user context)
    _store_oauth_state(state, code_verifier, str(current_user.id))

    # Compute PKCE code_challenge = BASE64URL(SHA256(code_verifier))
    code_challenge = (
        base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode("utf-8")).digest()
        )
        .rstrip(b"=")
        .decode("utf-8")
    )

    # Build authorization URL
    auth_url = (
        f"{_TELEGRAM_AUTH_URL}"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={_url_encode(REDIRECT_URI)}"
        f"&response_type=code"
        f"&scope={_url_encode(_OIDC_SCOPES)}"
        f"&state={state}"
        f"&code_challenge={code_challenge}"
        f"&code_challenge_method=S256"
    )

    await log_event(
        await _get_session(),
        "telegram.oidc_login_initiated",
        "Client initiated Telegram OIDC flow",
        user_id=current_user.id,
        payload={"telegram_username": getattr(current_user, "telegram_username", None)},
    )

    return {"url": auth_url}


@router.post("/callback-exchange")
async def client_telegram_callback_exchange(
    body: dict,
    session: AsyncSession = Depends(get_session),
):
    """Exchange Telegram OIDC authorization code for tokens and link account.

    Called by the Next.js API route that receives Telegram's redirect.
    The state parameter maps to the authenticated user server-side.
    """
    code = body.get("code", "")
    state = body.get("state", "")

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")

    # ── 1. Validate state ──────────────────────────────────────────────
    entry = _consume_oauth_state(state)
    if not entry:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired authorization state",
        )

    user_id = entry["user_id"]
    code_verifier = entry["code_verifier"]

    # ── 2. Exchange authorization code for tokens ──────────────────────
    credentials = base64.b64encode(
        f"{CLIENT_ID}:{CLIENT_SECRET}".encode("utf-8")
    ).decode("utf-8")

    async with httpx.AsyncClient() as http:
        token_resp = await http.post(
            _TELEGRAM_TOKEN_URL,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "client_id": CLIENT_ID,
                "code_verifier": code_verifier,
            },
            timeout=15,
        )

    if token_resp.status_code != 200:
        logger.error(
            "Telegram token exchange failed: status=%d body=%s",
            token_resp.status_code,
            token_resp.text[:200],
        )
        raise HTTPException(
            status_code=401,
            detail="Telegram authorization failed",
        )

    token_data = token_resp.json()
    id_token_str = token_data.get("id_token")
    if not id_token_str:
        raise HTTPException(
            status_code=401,
            detail="No ID token in Telegram response",
        )

    # ── 3. Validate ID token (RS256 signature + claims) ────────────────
    try:
        claims = _validate_id_token(id_token_str)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Telegram authorization expired")
    except jwt.InvalidAudienceError:
        raise HTTPException(status_code=401, detail="Invalid Telegram audience")
    except jwt.InvalidIssuerError:
        raise HTTPException(status_code=401, detail="Invalid Telegram issuer")
    except ValueError as e:
        logger.error("Telegram ID token validation failed: %s", e)
        raise HTTPException(status_code=401, detail="Telegram authorization verification failed")
    except Exception as e:
        logger.error("Unexpected ID token error: %s", e)
        raise HTTPException(status_code=401, detail="Telegram authorization verification failed")

    # ── 4. Extract Telegram user info ──────────────────────────────────
    telegram_id = claims.get("id") or claims.get("sub")
    if not telegram_id:
        raise HTTPException(status_code=401, detail="No Telegram user ID in token")

    telegram_id = int(telegram_id)
    telegram_username = str(claims.get("preferred_username", ""))[:120] or None
    telegram_name = str(claims.get("name", "")) or None

    # ── 5. Link account ────────────────────────────────────────────────
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Cross-account guard
    result2 = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    existing = result2.scalar_one_or_none()
    if existing and str(existing.id) != str(user.id):
        await log_event(
            session, "telegram.oidc_rejected",
            "Telegram account already linked to another client",
            user_id=user.id, severity="WARNING",
            payload={"tg_id": telegram_id, "owner_id": str(existing.id)},
        )
        await session.commit()
        raise HTTPException(
            status_code=409,
            detail="This Telegram account is already linked to another client",
        )

    was_connected = user.telegram_id is not None
    user.telegram_id = telegram_id
    user.telegram_username = telegram_username

    # Clean legacy bind-code data
    prefs = dict(user.preferences or {})
    prefs.pop("telegram_bind", None)
    user.preferences = prefs

    await log_event(
        session, "telegram.oidc_connected",
        "Telegram account linked via OIDC authorization code flow",
        user_id=user.id,
        payload={
            "telegram_id": telegram_id,
            "username": telegram_username,
            "name": telegram_name,
            "was_connected": was_connected,
        },
    )
    await session.commit()

    return {
        "success": True,
        "telegram_id": telegram_id,
        "telegram_username": telegram_username,
    }


@router.post("/disconnect")
async def client_telegram_disconnect(
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Unlink the Telegram chat. Preserves audit history."""
    chat_id = current_user.telegram_id
    current_user.telegram_id = None
    current_user.telegram_username = None
    prefs = dict(current_user.preferences or {})
    prefs.pop("telegram_bind", None)
    current_user.preferences = prefs
    await log_event(
        session, "telegram.disconnected",
        "Client unlinked Telegram chat",
        user_id=current_user.id,
        payload={"chat_id": chat_id},
    )
    await session.commit()
    return {"message": "Telegram disconnected", "connected": False}


@router.patch("/preferences")
async def client_telegram_preferences(
    body: dict,
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Update notification toggles and/or the interface language."""
    notifications = body.get("notifications") or {}
    if not isinstance(notifications, dict):
        raise HTTPException(status_code=400, detail="notifications must be an object")
    invalid = set(notifications.keys()) - NOTIF_KEYS
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid notification keys: {sorted(invalid)}",
        )

    language = body.get("language")
    if language is not None:
        language = str(language).upper()
        if language not in LANGUAGES:
            raise HTTPException(
                status_code=400,
                detail="Invalid language. Use EN, AR, FR or ES",
            )
        current_user.language = language

    prefs = dict(current_user.preferences or {})
    notifs = dict(prefs.get("notifications") or {})
    for key, val in notifications.items():
        notifs[key] = bool(val)
    prefs["notifications"] = notifs
    current_user.preferences = prefs

    await log_event(
        session, "telegram.preferences",
        "Client updated Telegram preferences",
        user_id=current_user.id,
        payload={"keys": sorted(notifications.keys())},
    )
    await session.commit()
    return {
        "message": "Preferences saved",
        "notifications": notifs,
        "language": current_user.language,
    }


@router.post("/test")
async def client_telegram_test(
    current_user=Depends(get_current_user),
):
    """Send a test notification to the linked chat."""
    if current_user.telegram_id is None:
        raise HTTPException(status_code=400, detail="Telegram is not connected")

    if os.getenv("TELEGRAM_TEST_MODE", "").lower() == "true":
        return {
            "message": "Test notification sent (test mode)",
            "chat_id": current_user.telegram_id,
        }

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise HTTPException(
            status_code=400, detail="Telegram bot is not configured"
        )

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                json={
                    "chat_id": current_user.telegram_id,
                    "text": "Test notification from ICT Funded Pro Bot.",
                },
                timeout=10,
            )
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Telegram send failed")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=502, detail=f"Telegram send failed: {e}"
        )

    return {"message": "Test notification sent", "chat_id": current_user.telegram_id}


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _url_encode(s: str) -> str:
    """URL-encode a string (stdlib, no import needed at top)."""
    from urllib.parse import quote
    return quote(s, safe="")


async def _get_session():
    """Get a DB session for logging in login endpoint (no DI context)."""
    from database.db import async_session_factory
    async with async_session_factory() as session:
        return session

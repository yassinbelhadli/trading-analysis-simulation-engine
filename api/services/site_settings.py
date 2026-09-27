"""Site settings — dashboard-editable key/value configuration.

Storage: `site_settings` table (key -> JSON value). This service holds the
authoritative schema (categories, types, defaults), merges DB overrides with
defaults, validates updates and encrypts secrets before persisting.

Consumers (telegram, email, engine, renderer...) read effective values via
`get_effective_settings` and fall back to their existing hardcoded defaults
when a key is absent — so wiring categories one by one is safe.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import SiteSetting
from security.encryption import decrypt, encrypt

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema  (key is fully qualified: "<category>.<name>")
# ---------------------------------------------------------------------------
SETTINGS_SCHEMA: List[Dict[str, Any]] = [
    # ── Appearance ───────────────────────────────────────────────
    {"key": "appearance.theme", "category": "appearance", "type": "select",
     "label": "Default theme", "options": ["dark", "light", "system"], "default": "dark"},
    {"key": "appearance.accent_color", "category": "appearance", "type": "color",
     "label": "Accent color", "default": "#3b82f6"},
    {"key": "appearance.brand_name", "category": "appearance", "type": "string",
     "label": "Brand name", "default": "ICT EA Pro"},
    {"key": "appearance.logo_url", "category": "appearance", "type": "string",
     "label": "Logo URL", "default": "", "help": "Public URL of the logo image."},

    # ── Telegram ─────────────────────────────────────────────────
    {"key": "telegram.enabled", "category": "telegram", "type": "boolean",
     "label": "Telegram bot enabled", "default": True},
    {"key": "telegram.default_language", "category": "telegram", "type": "select",
     "label": "Default language", "options": ["EN", "AR", "FR", "ES"], "default": "EN"},
    {"key": "telegram.welcome_message", "category": "telegram", "type": "textarea",
     "label": "Welcome message", "default": "Welcome to ICT EA Pro!"},
    {"key": "telegram.main_menu_message", "category": "telegram", "type": "textarea",
     "label": "Main menu message", "default": "Choose an option below."},
    {"key": "telegram.support_message", "category": "telegram", "type": "textarea",
     "label": "Support message", "default": "How can we help you today?"},
    {"key": "telegram.signal_include_chart", "category": "telegram", "type": "boolean",
     "label": "Signals include chart", "default": True},

    # ── Email ────────────────────────────────────────────────────
    {"key": "email.smtp_host", "category": "email", "type": "string",
     "label": "SMTP host", "default": "smtp.gmail.com"},
    {"key": "email.smtp_port", "category": "email", "type": "number",
     "label": "SMTP port", "default": 587},
    {"key": "email.smtp_user", "category": "email", "type": "string",
     "label": "SMTP user", "default": ""},
    {"key": "email.smtp_pass", "category": "email", "type": "password",
     "label": "SMTP password", "default": "", "is_secret": True},
    {"key": "email.smtp_from", "category": "email", "type": "string",
     "label": "From address", "default": "admin@ictfundedeapro.com"},
    {"key": "email.support_address", "category": "email", "type": "string",
     "label": "Support inbox", "default": "support@ictfundedeapro.com",
     "help": "Client tickets are forwarded to this inbox."},
    {"key": "email.billing_address", "category": "email", "type": "string",
     "label": "Billing sender", "default": "billing@ictfundedeapro.com",
     "help": "Payments and subscription notices are sent from this address."},
    {"key": "email.frontend_url", "category": "email", "type": "string",
     "label": "Frontend URL", "default": "http://localhost:3000"},
    {"key": "email.template_welcome", "category": "email", "type": "textarea",
     "label": "Welcome email template", "default": ""},
    {"key": "email.template_payment", "category": "email", "type": "textarea",
     "label": "Payment success template", "default": ""},
    {"key": "email.template_expiring", "category": "email", "type": "textarea",
     "label": "Subscription expiring template", "default": ""},
    {"key": "email.template_expired", "category": "email", "type": "textarea",
     "label": "Subscription expired template", "default": ""},
    {"key": "email.template_reset", "category": "email", "type": "textarea",
     "label": "Password reset template", "default": ""},
    {"key": "email.template_license", "category": "email", "type": "textarea",
     "label": "License activated template", "default": ""},

    # ── Trading ──────────────────────────────────────────────────
    {"key": "trading.max_risk_per_trade", "category": "trading", "type": "number",
     "label": "Max risk per trade (%)", "default": 1.0},
    {"key": "trading.max_daily_loss", "category": "trading", "type": "number",
     "label": "Max daily loss (%)", "default": 3.0},
    {"key": "trading.max_drawdown", "category": "trading", "type": "number",
     "label": "Max drawdown (%)", "default": 10.0},
    {"key": "trading.news_block_before_min", "category": "trading", "type": "number",
     "label": "Block before news (min)", "default": 60},
    {"key": "trading.news_block_after_min", "category": "trading", "type": "number",
     "label": "Block after news (min)", "default": 30},
    {"key": "trading.news_block_high_only", "category": "trading", "type": "boolean",
     "label": "Block high-impact news only", "default": True},
    {"key": "trading.session_filter_enabled", "category": "trading", "type": "boolean",
     "label": "Session filter enabled", "default": False},

    # ── Renderer ─────────────────────────────────────────────────
    {"key": "renderer.chart_theme", "category": "renderer", "type": "select",
     "label": "Chart theme", "options": ["dark", "light"], "default": "dark"},
    {"key": "renderer.chart_width", "category": "renderer", "type": "number",
     "label": "Chart width", "default": 1600},
    {"key": "renderer.chart_height", "category": "renderer", "type": "number",
     "label": "Chart height", "default": 900},

    # ── Symbols / Timeframes / Sessions ──────────────────────────
    {"key": "symbols.enabled", "category": "symbols", "type": "json",
     "label": "Enabled symbols", "default": ["XAUUSD", "NAS100", "BTCUSD"],
     "help": "JSON array of enabled symbols."},
    {"key": "timeframes.enabled", "category": "timeframes", "type": "json",
     "label": "Enabled timeframes", "default": ["M5", "M15", "H1", "H4"],
     "help": "JSON array of enabled timeframes."},
    {"key": "sessions.ict", "category": "sessions", "type": "json",
     "label": "ICT sessions (UTC)", "default": {"asian": ["00:00", "08:00"],
                                                 "london": ["07:00", "16:00"],
                                                 "newyork": ["12:00", "21:00"]}},

    # ── News ─────────────────────────────────────────────────────
    {"key": "news.provider", "category": "news", "type": "select",
     "label": "News provider", "options": ["forexfactory", "ff_calendar", "manual"],
     "default": "forexfactory"},
    {"key": "news.refresh_minutes", "category": "news", "type": "number",
     "label": "Refresh interval (min)", "default": 60},

    # ── API ──────────────────────────────────────────────────────
    {"key": "api.jwt_access_expire_minutes", "category": "api", "type": "number",
     "label": "Access token TTL (min)", "default": 30},
    {"key": "api.jwt_refresh_expire_days", "category": "api", "type": "number",
     "label": "Refresh token TTL (days)", "default": 30},

    # ── Workers ──────────────────────────────────────────────────
    {"key": "workers.engine_interval_seconds", "category": "workers", "type": "number",
     "label": "Engine scan interval (s)", "default": 5},
    {"key": "workers.heartbeat_interval_seconds", "category": "workers", "type": "number",
     "label": "Heartbeat interval (s)", "default": 30},
]

_SCHEMA_BY_KEY = {s["key"]: s for s in SETTINGS_SCHEMA}
_CATEGORY_ORDER = [
    "appearance", "telegram", "email", "trading", "renderer",
    "symbols", "timeframes", "sessions", "news", "api", "workers",
]


def get_settings_schema() -> Dict[str, Any]:
    """Schema grouped by category for the dashboard settings UI."""
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for s in SETTINGS_SCHEMA:
        entry = {k: v for k, v in s.items() if k != "category"}
        groups.setdefault(s["category"], []).append(entry)
    return {"categories": _CATEGORY_ORDER, "groups": groups}


def _coerce(value: Any, spec: Dict[str, Any]) -> Any:
    t = spec.get("type")
    if t == "boolean":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on")
        return bool(value)
    if t == "number":
        return float(value)
    if t in ("string", "select", "color", "password", "textarea"):
        return str(value)
    if t == "json":
        return value
    return value


async def get_effective_settings(
    session: AsyncSession, decrypt_secrets: bool = False
) -> Dict[str, Any]:
    """Defaults merged with DB overrides. Always returns every schema key."""
    result = await session.execute(select(SiteSetting))
    rows = {r.key: r for r in result.scalars().all()}
    merged: Dict[str, Any] = {}
    for spec in SETTINGS_SCHEMA:
        row = rows.get(spec["key"])
        if row is not None and row.value is not None:
            val = row.value
            if spec.get("is_secret") and decrypt_secrets and isinstance(val, str):
                if val.startswith("enc:"):
                    try:
                        val = decrypt(val[4:])
                    except Exception:
                        val = spec["default"]
            merged[spec["key"]] = _coerce(val, spec)
        else:
            merged[spec["key"]] = spec["default"]
    return merged


async def update_settings(
    session: AsyncSession,
    updates: Dict[str, Any],
    actor_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Validate + persist partial updates. Secrets are encrypted. Returns
    the effective values after the update (secrets returned decrypted)."""
    result = await session.execute(select(SiteSetting))
    existing = {r.key: r for r in result.scalars().all()}
    now = datetime.now(timezone.utc)

    saved: Dict[str, Any] = {}
    for key, raw_value in updates.items():
        spec = _SCHEMA_BY_KEY.get(key)
        if not spec:
            raise KeyError(f"Unknown setting: {key}")
        value = _coerce(raw_value, spec)
        payload = value
        if spec.get("is_secret") and isinstance(value, str):
            if value.startswith("enc:"):
                payload = value
                value = decrypt(value[4:]) if value[4:] else spec["default"]
            elif value:
                payload = "enc:" + encrypt(value)
            else:
                value = spec["default"]
                payload = value

        row = existing.get(key)
        if row is None:
            row = SiteSetting(
                key=key,
                value=payload,
                category=spec["category"],
                is_secret=bool(spec.get("is_secret")),
                updated_at=now,
                updated_by=actor_id,
            )
            session.add(row)
        else:
            row.value = payload
            row.is_secret = bool(spec.get("is_secret"))
            row.updated_at = now
            row.updated_by = actor_id
        saved[key] = value
    await session.commit()
    return saved

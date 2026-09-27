"""Notification preferences — single source of truth for the per-user toggles.

The client Telegram route (`api/routes/client/telegram.py`) stores these keys
in `user.preferences.notifications`. This module is the canonical definition so
the delivery pipeline and the API can never disagree about valid keys.
"""
from __future__ import annotations

from typing import Any

# Valid notification keys (mirrors client portal toggles).
NOTIF_KEYS = {"signals", "filled", "tp", "sl", "news", "weekly_report", "monthly_report"}

# Default state — everything on.
DEFAULT_NOTIFICATIONS = {
    "signals": True,
    "filled": True,
    "tp": True,
    "sl": True,
    "news": True,
    "weekly_report": True,
    "monthly_report": True,
}


def get_user_notifications(user: Any) -> dict:
    """Effective notification preferences for a user (defaults + stored overrides).

    Unknown keys are ignored so stale JSON can never enable anything unexpected.
    """
    merged = dict(DEFAULT_NOTIFICATIONS)
    stored = (getattr(user, "preferences", None) or {}).get("notifications") or {}
    merged.update({k: bool(v) for k, v in stored.items() if k in NOTIF_KEYS})
    return merged


def wants_notification(user: Any, key: str) -> bool:
    """True if the user wants notifications for `key` (defaults to True)."""
    return bool(get_user_notifications(user).get(key, True))

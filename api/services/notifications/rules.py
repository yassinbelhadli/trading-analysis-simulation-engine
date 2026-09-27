"""Rule engine — decides which channels an event should use.

Routing is intentional and small: trade/news events go to Telegram (gated by
the per-user toggles), license lifecycle events go to Email, and system alerts
always go to Telegram. The dispatch audit record is written by the dispatcher
for every event regardless of routing.
"""
from __future__ import annotations

from typing import Dict, List

# Event → notification-preference key gate (Telegram).
TELEGRAM_PREF_KEYS: Dict[str, str] = {
    "SETUP_DETECTED": "signals",
    "PAPER_TRADE_PLANNED": "signals",
    "TRADE_BLOCKED": "signals",
    "TRADE_OPENED": "filled",
    "PAPER_TRADE_FILLED": "filled",
    "BREAK_EVEN_MOVED": "filled",
    "TRAILING_STOP_UPDATED": "filled",
    "TP_HIT": "tp",
    "PAPER_TRADE_TP_HIT": "tp",
    "SL_HIT": "sl",
    "PAPER_TRADE_SL_HIT": "sl",
    "TRADE_CLOSED": "tp",
    "PARTIAL_CLOSE": "tp",
    "NEWS_UPDATED": "news",
    "NEWS_COUNTDOWN": "news",
    "WEEKLY_REPORT": "weekly_report",
    "MONTHLY_REPORT": "monthly_report",
    # Economic calendar alerts
    "CALENDAR_UPDATED": "news",
    "ECONOMIC_EVENT_CREATED": "news",
    "ECONOMIC_EVENT_UPDATED": "news",
    "ECONOMIC_EVENT_RELEASED": "news",
    "CALENDAR_T60_ALERT": "news",
    "CALENDAR_T30_ALERT": "news",
    "CALENDAR_T5_ALERT": "news",
    "CALENDAR_WEEKLY_SUMMARY": "weekly_report",
    "CALENDAR_DATA_UNAVAILABLE": "news",
}

# System alerts — always delivered to Telegram (not user-gated).
SYSTEM_EVENTS = {"ERROR", "HEALTH_WARNING", "SYSTEM_INFO", "HEALTH_STATUS_CHANGE"}

# Email-routed lifecycle events (no preference gate today).
EMAIL_EVENTS = {"LICENSE_ACTIVATED", "LICENSE_EXPIRED", "LICENSE_WARNING"}


def resolve_channels(event_type: str, notifications: Dict[str, bool]) -> List[str]:
    """Ordered channel list for an event, honouring per-user notification toggles."""
    channels: List[str] = []
    pref_key = TELEGRAM_PREF_KEYS.get(event_type)
    if pref_key is not None:
        if notifications.get(pref_key, True):
            channels.append("telegram")
    elif event_type in SYSTEM_EVENTS:
        channels.append("telegram")
    if event_type in EMAIL_EVENTS:
        channels.append("email")
    return channels

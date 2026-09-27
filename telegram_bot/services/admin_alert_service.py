"""AdminAlertService — sends critical system alerts to admin Telegram chat."""

from __future__ import annotations

import logging
import os
from typing import Optional

from telegram import Bot
from telegram.constants import ParseMode

from core_engine.events.event_bus import event_bus
from core_engine.events.event_types import EventType

logger = logging.getLogger(__name__)

ADMIN_EVENTS = {
    EventType.LICENSE_EXPIRED.value,
    EventType.ACCOUNT_DISCONNECTED.value,
    EventType.ENGINE_ERROR.value,
    EventType.ERROR.value,
    EventType.HEALTH_WARNING.value,
    EventType.SYSTEM_ERROR.value,
}


class AdminAlertService:
    """Monitors critical system events and alerts the admin."""

    def __init__(self, bot: Bot, admin_chat_id: Optional[int] = None):
        self.bot = bot
        self.admin_chat_id = admin_chat_id or _get_admin_chat_id()
        self._subscribed = False

    def start(self):
        if self._subscribed:
            return
        if not self.admin_chat_id:
            logger.warning("AdminAlertService: no ADMIN_CHAT_ID configured, skipping")
            return
        for ev in ADMIN_EVENTS:
            event_bus.subscribe(ev, self._on_event)
        self._subscribed = True
        logger.info("AdminAlertService subscribed to %d event types", len(ADMIN_EVENTS))

    def stop(self):
        if not self._subscribed:
            return
        for ev in ADMIN_EVENTS:
            event_bus.unsubscribe(ev, self._on_event)
        self._subscribed = False

    def _on_event(self, data: dict):
        import asyncio
        asyncio.create_task(self._dispatch(data))

    async def _dispatch(self, data: dict):
        event_type = data.get("event_type", "")
        message = data.get("message", "")
        payload = data.get("data", {})

        icon_map = {
            EventType.LICENSE_EXPIRED.value: "\U0001f6ab",
            EventType.ACCOUNT_DISCONNECTED.value: "\u26a0\ufe0f",
            EventType.ENGINE_ERROR.value: "\u274c",
            EventType.ERROR.value: "\u274c",
            EventType.HEALTH_WARNING.value: "\u26a0\ufe0f",
            EventType.SYSTEM_ERROR.value: "\u274c",
        }
        label_map = {
            EventType.LICENSE_EXPIRED.value: "License Expired",
            EventType.ACCOUNT_DISCONNECTED.value: "MT5 Disconnected",
            EventType.ENGINE_ERROR.value: "Engine Error",
            EventType.ERROR.value: "System Error",
            EventType.HEALTH_WARNING.value: "Health Warning",
            EventType.SYSTEM_ERROR.value: "API Offline",
        }

        icon = icon_map.get(event_type, "\u26a0\ufe0f")
        label = label_map.get(event_type, event_type.replace("_", " ").title())
        account_id = payload.get("account_id", data.get("account_id", ""))

        lines = [
            f"{icon} <b>{label}</b>",
            "",
            f"{message}",
        ]
        if account_id:
            lines.append(f"Account: <code>{account_id}</code>")

        text = "\n".join(lines)
        try:
            await self.bot.send_message(
                chat_id=self.admin_chat_id,
                text=text,
                parse_mode=ParseMode.HTML,
            )
            logger.info("Admin alert sent: %s", label)
        except Exception as e:
            logger.error("Failed to send admin alert: %s", e)


def _get_admin_chat_id() -> Optional[int]:
    raw = os.getenv("ADMIN_CHAT_ID", os.getenv("TELEGRAM_CHAT_ID", ""))
    try:
        return int(raw.strip())
    except (ValueError, AttributeError):
        return None

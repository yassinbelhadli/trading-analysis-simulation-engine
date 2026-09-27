"""Channel abstraction — Telegram, Email and the audit sink.

Every provider is behind an interface with a mock/test mode so QA and CI never
touch real providers (same pattern as `TELEGRAM_TEST_MODE` and FakeSMTP).
Delivery never raises — it returns a `ChannelResult`.
"""
from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class ChannelResult:
    """Outcome of a single delivery attempt."""

    __slots__ = ("channel", "ok", "status", "detail")

    def __init__(self, channel: str, ok: bool, status: str, detail: str = ""):
        self.channel = channel
        self.ok = ok
        self.status = status  # delivered | skipped | not_configured | failed
        self.detail = detail

    def to_dict(self) -> dict:
        return {"channel": self.channel, "ok": self.ok,
                "status": self.status, "detail": self.detail}


class BaseChannel(ABC):
    name: str = ""

    @abstractmethod
    async def deliver(self, **kwargs: Any) -> ChannelResult:
        ...


def _test_mode() -> bool:
    return os.getenv("TELEGRAM_TEST_MODE", "").lower() == "true"


class TelegramChannel(BaseChannel):
    name = "telegram"

    async def deliver(self, *, chat_id: Optional[int] = None, text: str = "",
                      parse_mode: str = "HTML") -> ChannelResult:
        if not chat_id:
            return ChannelResult(self.name, False, "skipped", "no chat_id")
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if _test_mode():
            logger.info("Telegram test mode — message to %s mocked", chat_id)
            return ChannelResult(self.name, True, "delivered", "mocked")
        if not token:
            return ChannelResult(self.name, False, "not_configured",
                                 "TELEGRAM_BOT_TOKEN is not set")
        try:
            import httpx
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, json={
                    "chat_id": chat_id, "text": text, "parse_mode": parse_mode,
                })
            if resp.status_code == 200:
                return ChannelResult(self.name, True, "delivered")
            return ChannelResult(self.name, False, "failed", f"http {resp.status_code}")
        except Exception as e:
            logger.error("Telegram deliver failed to %s: %s", chat_id, e)
            return ChannelResult(self.name, False, "failed", str(e))


class EmailChannel(BaseChannel):
    name = "email"

    async def deliver(self, *, to: Optional[str] = None, subject: str = "",
                      body: str = "", session: Optional[AsyncSession] = None) -> ChannelResult:
        if not to:
            return ChannelResult(self.name, False, "skipped", "no recipient")
        if os.getenv("EMAIL_TEST_MODE", "").lower() == "true":
            logger.info("Email test mode — mail to %s mocked", to)
            return ChannelResult(self.name, True, "delivered", "mocked")
        try:
            from api.services.email_service import send_email
            ok = await send_email(to, subject, body, session=session)
            if ok:
                return ChannelResult(self.name, True, "delivered")
            return ChannelResult(self.name, False, "failed", "smtp send failed")
        except Exception as e:
            logger.error("Email deliver failed to %s: %s", to, e)
            return ChannelResult(self.name, False, "failed", str(e))


class AuditChannel(BaseChannel):
    """Persisted delivery log — writes to the existing audit_logs table so no
    schema change is required for 6.0 (a dedicated table may come later)."""

    name = "audit"

    async def deliver(self, *, session: Optional[AsyncSession] = None,
                      event_type: str = "", user_id: Optional[str] = None,
                      message: str = "", payload: Optional[dict] = None) -> ChannelResult:
        if session is None:
            return ChannelResult(self.name, False, "skipped", "no session")
        try:
            from security.audit import log_event
            audit_id = await log_event(
                session, "notification.delivery", message,
                user_id=user_id, severity="INFO", source="notification",
                payload=payload or {},
            )
            return ChannelResult(self.name, True, "delivered", audit_id)
        except Exception as e:
            logger.error("Audit deliver failed: %s", e)
            return ChannelResult(self.name, False, "failed", str(e))


def channel_registry() -> dict:
    """Fresh registry (lazy — no bot/network at import time)."""
    return {
        "telegram": TelegramChannel(),
        "email": EmailChannel(),
        "audit": AuditChannel(),
    }

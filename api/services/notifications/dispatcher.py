"""Dispatcher — orchestrates rule → channel → template → delivery → audit.

6.0 provides the pipeline; it is not auto-started anywhere yet. Phase 6.2 wires
it to the production runtimes (background_runner / bot post_init). QA exercises
`dispatch` and `broadcast` directly with mock channels.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from api.services.notifications.channels import BaseChannel, channel_registry
from api.services.notifications.preferences import get_user_notifications
from api.services.notifications.rules import resolve_channels
from api.services.notifications.templates import (
    render_email_body,
    render_email_subject,
    render_telegram,
)

logger = logging.getLogger(__name__)


class NotificationDispatcher:
    def __init__(self, registry: Optional[Dict[str, BaseChannel]] = None):
        self._registry = registry or channel_registry()

    def channel(self, name: str) -> Optional[BaseChannel]:
        return self._registry.get(name)

    async def dispatch(
        self,
        session: AsyncSession,
        *,
        user: Any,
        event_type: str,
        payload: Optional[dict] = None,
        message: str = "",
        severity: str = "INFO",
    ) -> dict:
        """Route one event to the channels the user should receive it on.

        Always writes a `notification.delivery` audit record (the persisted
        delivery log). Returns a per-channel result summary.
        """
        payload = payload or {}
        prefs = get_user_notifications(user)
        channels = resolve_channels(event_type, prefs)
        lang = (getattr(user, "language", None) or "EN").upper()
        results: List[dict] = []

        if "telegram" in channels:
            chat_id = getattr(user, "telegram_id", None)
            if chat_id:
                text = render_telegram(event_type, payload, message, lang)
                res = await self._registry["telegram"].deliver(chat_id=int(chat_id), text=text)
            else:
                res = _skip_result("telegram", "no linked chat")
            results.append(res.to_dict())

        if "email" in channels:
            email = getattr(user, "email", None)
            if email:
                subject = render_email_subject(event_type, lang)
                body = render_email_body(event_type, payload, message, lang)
                res = await self._registry["email"].deliver(
                    to=email, subject=subject, body=body, session=session)
            else:
                res = _skip_result("email", "no email address")
            results.append(res.to_dict())

        audit_id = await self._log_delivery(
            session, user_id=getattr(user, "id", None), event_type=event_type,
            channels=channels, results=results, severity=severity,
            message=message or event_type,
        )
        return {
            "event_type": event_type,
            "channels": channels,
            "results": results,
            "audit_id": audit_id,
        }

    async def broadcast(
        self,
        session: AsyncSession,
        *,
        recipients: List[Any],
        event_type: str,
        payload: Optional[dict] = None,
        message: str = "",
        lang: str = "EN",
        severity: str = "INFO",
    ) -> dict:
        """Fan-out a message to every recipient that has a linked Telegram chat.

        `recipients` are User-like objects. Non-telegram users are counted as
        skipped. One summary audit record is written.
        """
        payload = payload or {}
        lang = lang.upper()
        sent = 0
        skipped = 0
        failures = 0
        text = render_telegram(event_type, payload, message, lang)
        delivered_ids: List[str] = []
        for r in recipients:
            chat_id = getattr(r, "telegram_id", None)
            if not chat_id:
                skipped += 1
                continue
            res = await self._registry["telegram"].deliver(chat_id=int(chat_id), text=text)
            if res.ok:
                sent += 1
                uid = getattr(r, "id", None)
                if uid:
                    delivered_ids.append(uid)
            else:
                failures += 1
        results = [{"channel": "telegram", "ok": True, "status": "delivered", "detail": f"{sent} recipients"}]
        if failures:
            results.append({"channel": "telegram", "ok": False, "status": "failed", "detail": f"{failures} recipients"})
        audit_id = await self._log_delivery(
            session, user_id=None, event_type=event_type, channels=["telegram"],
            results=results, severity=severity, message=f"broadcast: {message or event_type}",
            extra_payload={"sent": sent, "skipped": skipped, "failures": failures},
        )
        return {"sent": sent, "skipped": skipped, "failures": failures, "audit_id": audit_id}

    async def _log_delivery(
        self, session: AsyncSession, *, user_id, event_type: str,
        channels: List[str], results: List[dict], severity: str,
        message: str, extra_payload: Optional[dict] = None,
    ) -> str:
        audit = self._registry.get("audit")
        if audit is None:
            return ""
        payload = {"event_type": event_type, "channels": channels,
                   "results": results}
        if extra_payload:
            payload.update(extra_payload)
        res = await audit.deliver(
            session=session, event_type=event_type, user_id=user_id,
            message=f"Notification dispatched: {message}", payload=payload)
        return res.detail or ""


def _skip_result(channel: str, reason: str):
    from api.services.notifications.channels import ChannelResult
    return ChannelResult(channel, False, "skipped", reason)


notification_dispatcher = NotificationDispatcher()

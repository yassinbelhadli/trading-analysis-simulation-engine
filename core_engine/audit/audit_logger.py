from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from database.db import async_session_factory
from database.models import AuditLog
from database.repositories import AuditRepository
from core_engine.events.event_bus import event_bus
from core_engine.events.event_types import EventType, EVENT_SEVERITY

logger = logging.getLogger(__name__)


class AuditLogger:
    def __init__(self):
        self._subscribed = False
        self._source_mapping: Dict[str, str] = {
            EventType.BOT_STARTED.value: "system",
            EventType.BOT_STOPPED.value: "system",
            EventType.LICENSE_ACTIVATED.value: "license",
            EventType.LICENSE_EXPIRED.value: "license",
            EventType.LICENSE_WARNING.value: "license",
            EventType.ACCOUNT_CONNECTED.value: "scanner",
            EventType.ACCOUNT_DISCONNECTED.value: "scanner",
            EventType.ACCOUNT_RECONNECTED.value: "scanner",
            EventType.SCANNER_STARTED.value: "scanner",
            EventType.SCANNER_STOPPED.value: "scanner",
            EventType.ENGINE_STARTED.value: "engine",
            EventType.ENGINE_STOPPED.value: "engine",
            EventType.ENGINE_PAUSED.value: "engine",
            EventType.ENGINE_RESUMED.value: "engine",
            EventType.ENGINE_ERROR.value: "engine",
            EventType.TRADE_CREATED.value: "execution",
            EventType.TRADE_OPENED.value: "execution",
            EventType.TRADE_UPDATED.value: "execution",
            EventType.TRADE_CLOSED.value: "execution",
            EventType.TRADE_CANCELLED.value: "execution",
            EventType.TRADE_BLOCKED.value: "execution",
            EventType.ORDER_SENT.value: "execution",
            EventType.BREAK_EVEN_MOVED.value: "execution",
            EventType.PARTIAL_CLOSE.value: "execution",
            EventType.TRAILING_STOP_UPDATED.value: "execution",
            EventType.TP_HIT.value: "execution",
            EventType.SL_HIT.value: "execution",
            EventType.SETUP_DETECTED.value: "detection",
            EventType.CANDIDATE_FOUND.value: "detection",
            EventType.NO_SETUP.value: "detection",
            EventType.PAPER_TRADE_PLANNED.value: "papertrade",
            EventType.PAPER_TRADE_REJECTED.value: "papertrade",
            EventType.RISK_BREACH.value: "risk",
            EventType.RISK_CHECK.value: "risk",
            EventType.NEWS_UPDATED.value: "news",
            EventType.FUNDAMENTAL_STATE_UPDATED.value: "news",
            EventType.HEALTH_WARNING.value: "system",
            EventType.HEALTH_OK.value: "system",
            EventType.HEALTH_STATUS_CHANGE.value: "system",
            EventType.ERROR.value: "system",
            EventType.SYSTEM_INFO.value: "system",
            EventType.SYSTEM_ERROR.value: "system",
        }

    def start(self):
        if self._subscribed:
            return
        for ev in EventType:
            event_bus.subscribe(ev.value, self._on_event)
        self._subscribed = True
        logger.info(
            "AuditLogger subscribed to %d event types", len(EventType)
        )

    def stop(self):
        if not self._subscribed:
            return
        for ev in EventType:
            event_bus.unsubscribe(ev.value, self._on_event)
        self._subscribed = False

    def _on_event(self, data: Any):
        import asyncio
        asyncio.create_task(self._write_log(data))

    async def _write_log(self, data: Any):
        if not isinstance(data, dict):
            return
        event_type = data.get("event_type", "")
        account_id = data.get("account_id")
        user_id = data.get("user_id")
        message = data.get("message", "")
        payload = data.get("data") or data.get("payload") or {}
        severity = EVENT_SEVERITY.get(event_type, "INFO")
        if isinstance(severity, EventType):
            severity = severity.value
        source = self._source_mapping.get(event_type, "unknown")
        try:
            async with async_session_factory() as session:
                repo = AuditRepository(session)
                log = AuditLog(
                    account_id=account_id,
                    user_id=user_id,
                    event_type=event_type,
                    severity=severity,
                    source=source,
                    message=message[:2000],
                    payload_json=payload if isinstance(payload, dict) else {"raw": str(payload)},
                )
                await repo.add(log)
                await session.commit()
        except Exception as e:
            logger.error("Audit log write failed: %s", e)

    # ------------------------------------------------------------------
    # Direct logging helpers (for non-EventBus code paths)
    # ------------------------------------------------------------------

    async def log_event(
        self,
        event_type: str,
        message: str,
        account_id: Optional[str] = None,
        user_id: Optional[str] = None,
        payload: Optional[dict] = None,
        source: Optional[str] = None,
    ):
        severity = EVENT_SEVERITY.get(event_type, "INFO")
        if isinstance(severity, EventType):
            severity = severity.value
        try:
            async with async_session_factory() as session:
                repo = AuditRepository(session)
                log = AuditLog(
                    account_id=account_id,
                    user_id=user_id,
                    event_type=event_type,
                    severity=severity,
                    source=source or self._source_mapping.get(event_type, "unknown"),
                    message=message[:2000],
                    payload_json=payload,
                )
                await repo.add(log)
                await session.commit()
        except Exception as e:
            logger.error("Direct audit log failed: %s", e)

    async def log_error(
        self,
        message: str,
        account_id: Optional[str] = None,
        user_id: Optional[str] = None,
        payload: Optional[dict] = None,
    ):
        await self.log_event(
            EventType.ERROR.value, message,
            account_id=account_id, user_id=user_id, payload=payload,
            source="system",
        )

    async def log_trade(
        self,
        action: str,
        message: str,
        account_id: str,
        user_id: str,
        payload: Optional[dict] = None,
    ):
        await self.log_event(
            action, message,
            account_id=account_id, user_id=user_id, payload=payload,
            source="execution",
        )

    async def log_engine(
        self,
        action: str,
        message: str,
        account_id: str,
        user_id: str,
        payload: Optional[dict] = None,
    ):
        await self.log_event(
            action, message,
            account_id=account_id, user_id=user_id, payload=payload,
            source="engine",
        )

    async def log_risk(
        self,
        action: str,
        message: str,
        account_id: str,
        user_id: str,
        payload: Optional[dict] = None,
    ):
        await self.log_event(
            action, message,
            account_id=account_id, user_id=user_id, payload=payload,
            source="risk",
        )

    async def log_system(
        self,
        message: str,
        severity: str = "INFO",
        payload: Optional[dict] = None,
    ):
        event_type = {
            "CRITICAL": EventType.SYSTEM_ERROR.value,
            "ERROR": EventType.ERROR.value,
            "WARN": EventType.HEALTH_WARNING.value,
        }.get(severity, EventType.SYSTEM_INFO.value)
        await self.log_event(
            event_type, message,
            payload=payload, source="system",
        )


audit_logger = AuditLogger()

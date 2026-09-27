"""EventBus → NotificationDispatcher bridge.

Subscribes to the core EventBus and routes each event through the full
NotificationDispatcher pipeline (rules → channels → templates → delivery → audit).

Replaces the legacy AlertService for production use. The bridge adds:
  - Per-user notification preference enforcement (signals, fills, tp, sl, news …)
  - i18n template rendering (EN / AR / FR / ES)
  - Multi-channel routing (Telegram + Email)
  - Delivery audit logging
  - Dedup cooldown per symbol:direction
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, Optional, Set

from core_engine.events.event_bus import event_bus
from core_engine.events.event_types import EVENT_SEVERITY, EventType

logger = logging.getLogger(__name__)

# Every event type the bridge listens for.  Matches AlertService's original
# coverage so no notification is lost during the transition.
BRIDGE_EVENTS: Set[str] = {
    EventType.SETUP_DETECTED.value,
    EventType.PAPER_TRADE_PLANNED.value,
    EventType.TRADE_OPENED.value,
    EventType.TRADE_CLOSED.value,
    EventType.BREAK_EVEN_MOVED.value,
    EventType.PARTIAL_CLOSE.value,
    EventType.TRAILING_STOP_UPDATED.value,
    EventType.TP_HIT.value,
    EventType.SL_HIT.value,
    EventType.PAPER_TRADE_FILLED.value,
    EventType.PAPER_TRADE_TP_HIT.value,
    EventType.PAPER_TRADE_SL_HIT.value,
    EventType.TRADE_BLOCKED.value,
    EventType.NEWS_UPDATED.value,
    EventType.NEWS_COUNTDOWN.value,
    # Economic calendar events
    EventType.CALENDAR_UPDATED.value,
    EventType.ECONOMIC_EVENT_CREATED.value,
    EventType.ECONOMIC_EVENT_UPDATED.value,
    EventType.ECONOMIC_EVENT_RELEASED.value,
    EventType.CALENDAR_T60_ALERT.value,
    EventType.CALENDAR_T30_ALERT.value,
    EventType.CALENDAR_T5_ALERT.value,
    EventType.CALENDAR_WEEKLY_SUMMARY.value,
    EventType.CALENDAR_DATA_UNAVAILABLE.value,
    # System alerts
    EventType.ERROR.value,
    EventType.HEALTH_WARNING.value,
    EventType.SYSTEM_INFO.value,
}


class EventNotificationBridge:
    """Bridges the in-process EventBus to the NotificationDispatcher pipeline.

    Usage::

        bridge = EventNotificationBridge()
        bridge.start()   # subscribe to all events
        # … later …
        bridge.stop()    # unsubscribe
    """

    DEDUP_COOLDOWN = 1800  # seconds — same as legacy AlertService

    def __init__(self) -> None:
        self._subscribed = False
        self._last_sent: Dict[str, float] = {}

    # ── lifecycle ─────────────────────────────────────────────────

    def start(self) -> None:
        """Subscribe to every event type the bridge handles."""
        if self._subscribed:
            return
        for ev in BRIDGE_EVENTS:
            event_bus.subscribe(ev, self._on_event)
        self._subscribed = True
        logger.info(
            "EventNotificationBridge subscribed to %d event types",
            len(BRIDGE_EVENTS),
        )

    def stop(self) -> None:
        """Unsubscribe from the event bus."""
        if not self._subscribed:
            return
        for ev in BRIDGE_EVENTS:
            event_bus.unsubscribe(ev, self._on_event)
        self._subscribed = False
        logger.info("EventNotificationBridge stopped")

    # ── event handling ────────────────────────────────────────────

    def _on_event(self, data: dict) -> None:
        """Sync callback invoked by the EventBus — schedule the async work."""
        asyncio.create_task(self._dispatch(data))

    async def _dispatch(self, data: dict) -> None:
        """Look up the user, open a session, and route through the dispatcher."""
        user_id: str = data.get("user_id", "")
        event_type: str = data.get("event_type", "")
        payload: dict = data.get("data", {})
        message: str = data.get("message", "")

        if not user_id or not event_type:
            return

        # Dedup — prevent the same symbol:direction from being sent too often
        if event_type in (
            EventType.SETUP_DETECTED.value,
            EventType.PAPER_TRADE_PLANNED.value,
        ):
            dedup_key = f"{payload.get('symbol', '')}:{payload.get('direction', '')}"
            if dedup_key and not self._allow_send(dedup_key):
                logger.debug(
                    "Bridge dedup skipped: %s (%.0fs remaining)",
                    dedup_key,
                    self.DEDUP_COOLDOWN - (time.time() - self._last_sent.get(dedup_key, 0)),
                )
                return

        try:
            from api.services.notifications.dispatcher import notification_dispatcher
            from database.db import async_session_factory
            from database.repositories import UserRepository

            async with async_session_factory() as session:
                repo = UserRepository(session)
                user = await repo.get_by_id(user_id)
                if not user:
                    logger.debug("Bridge: user %s not found, skipping %s", user_id, event_type)
                    return

                severity = EVENT_SEVERITY.get(event_type, "INFO")

                result = await notification_dispatcher.dispatch(
                    session,
                    user=user,
                    event_type=event_type,
                    payload=payload,
                    message=message,
                    severity=severity,
                )

                # Commit the audit record written by the dispatcher.
                # log_event() only flushes; the bridge owns the transaction.
                await session.commit()

                channels = result.get("channels", [])
                if channels:
                    logger.info(
                        "Bridge dispatched %s → %s for user %s",
                        event_type,
                        channels,
                        user_id,
                    )
                else:
                    logger.debug(
                        "Bridge: %s not routed for user %s (preferences off)",
                        event_type,
                        user_id,
                    )
        except Exception as exc:
            logger.error(
                "EventNotificationBridge dispatch failed for %s: %s",
                event_type,
                exc,
                exc_info=True,
            )

    # ── dedup ─────────────────────────────────────────────────────

    def _allow_send(self, key: str) -> bool:
        now = time.time()
        last = self._last_sent.get(key, 0)
        if now - last < self.DEDUP_COOLDOWN:
            return False
        self._last_sent[key] = now
        return True


# ── Module-level singleton ────────────────────────────────────────
event_notification_bridge = EventNotificationBridge()

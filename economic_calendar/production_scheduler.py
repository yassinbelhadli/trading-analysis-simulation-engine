"""Production Calendar Scheduler — implements CalendarSchedulerInterface.

Responsibilities:
  - Check T-60 / T-30 / T-5 windows on each tick
  - Detect actual releases and update DB
  - Generate weekly summaries
  - Emit events via EventBus (consumed by EventNotificationBridge)
  - Track which alerts have been sent (dedup)
  - Maintain the NewsRiskWindow state

The scheduler runs as a background asyncio task started by api/main.py.
It does NOT send Telegram messages directly — it emits events through
the EventBus which the existing EventNotificationBridge handles.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set

from core_engine.events.event_bus import event_bus
from core_engine.events.event_types import EventType
from database.calendar_models import CalendarEvent
from database.db import async_session_factory
from economic_calendar.impact import ImpactClassifier
from economic_calendar.relevance import MarketRelevanceMapper
from economic_calendar.scheduler import CalendarAlert, CalendarSchedulerInterface, WeeklySummary
from economic_calendar.service import EconomicCalendarService
from core_engine.risk.news_risk_window import news_risk_window

logger = logging.getLogger(__name__)


class ProductionCalendarScheduler(CalendarSchedulerInterface):
    """Concrete scheduler that checks calendar events and emits alerts.

    Usage::

        scheduler = ProductionCalendarScheduler()
        await scheduler.start()
        # ... scheduler runs via check_loop() ...
        await scheduler.stop()
    """

    def __init__(
        self,
        calendar_service: Optional[EconomicCalendarService] = None,
        impact_classifier: Optional[ImpactClassifier] = None,
        relevance_mapper: Optional[MarketRelevanceMapper] = None,
        t60_minutes: float = 60.0,
        t30_minutes: float = 30.0,
        t5_minutes: float = 5.0,
        reaction_window_minutes: float = 15.0,
        check_interval_seconds: float = 60.0,
        fetch_interval_seconds: float = 3600.0,
    ):
        self.calendar_service = calendar_service or EconomicCalendarService()
        self.impact_classifier = impact_classifier or ImpactClassifier()
        self.relevance_mapper = relevance_mapper or MarketRelevanceMapper()
        self.t60_minutes = t60_minutes
        self.t30_minutes = t30_minutes
        self.t5_minutes = t5_minutes
        self.reaction_window_minutes = reaction_window_minutes
        self.check_interval_seconds = check_interval_seconds
        self.fetch_interval_seconds = fetch_interval_seconds

        # Dedup: set of event_ids already alerted for each window
        self._t60_alerted: Set[str] = set()
        self._t30_alerted: Set[str] = set()
        self._t5_alerted: Set[str] = set()
        self._released_emitted: Set[str] = set()
        self._weekly_sent: Optional[datetime] = None  # last Monday we sent for

        self._running = False
        self._task: Optional[object] = None  # asyncio.Task
        self._fetch_task: Optional[object] = None

    # ── Lifecycle ────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the scheduler loop as a background task."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._check_loop())
        self._fetch_task = asyncio.create_task(self._fetch_loop())
        logger.info(
            "ProductionCalendarScheduler started (check=%ds, fetch=%ds)",
            self.check_interval_seconds,
            self.fetch_interval_seconds,
        )

    async def stop(self) -> None:
        """Stop the scheduler loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._fetch_task:
            self._fetch_task.cancel()
            try:
                await self._fetch_task
            except asyncio.CancelledError:
                pass
            self._fetch_task = None
        logger.info("ProductionCalendarScheduler stopped")

    async def _check_loop(self) -> None:
        """Main check loop -- runs every check_interval_seconds."""
        while self._running:
            try:
                now = datetime.now(timezone.utc)

                # T-60: block new entries
                t60_alerts = await self.check_t60_window(now)
                for alert in t60_alerts:
                    self._emit_t60(alert)

                # T-30: pre-release notification
                t30_alerts = await self.check_t30_alerts(now)
                for alert in t30_alerts:
                    self._emit_t30(alert)

                # T-5: imminent release notification
                t5_alerts = await self.check_t5_alerts(now)
                for alert in t5_alerts:
                    self._emit_t5(alert)

                # Release detection
                released = await self.check_actual_release(now)
                for alert in released:
                    self._emit_released(alert)

                # Reaction window transitions
                self._check_reaction_windows(now)

                # Cleanup stale events
                news_risk_window.cleanup_stale(now)

                # Weekly summary (once per Monday)
                if now.weekday() == 0 and self._should_send_weekly(now):
                    summary = await self.generate_weekly_summary(now)
                    if summary:
                        self._emit_weekly(summary)

            except Exception as e:
                logger.error("Calendar check_loop error: %s", e, exc_info=True)

            await asyncio.sleep(self.check_interval_seconds)

    async def _fetch_loop(self) -> None:
        """Periodic fetch loop -- re-fetches calendar data."""
        # Initial fetch after 30 seconds
        await asyncio.sleep(30)
        while self._running:
            try:
                stats = await self.calendar_service.fetch_and_upsert()
                if stats.get("created", 0) > 0 or stats.get("updated", 0) > 0:
                    logger.info("Calendar fetch: %s", stats)
            except Exception as e:
                logger.error("Calendar fetch_loop error: %s", e)
            await asyncio.sleep(self.fetch_interval_seconds)

    # ── T-60 Window ──────────────────────────────────────────────

    async def check_t60_window(self, now: Optional[datetime] = None) -> List[CalendarAlert]:
        """Find HIGH/MEDIUM events entering the T-60 window."""
        now = now or datetime.now(timezone.utc)
        window_end = now + timedelta(minutes=self.t60_minutes + 1)

        events = await self._query_events_in_window(now, window_end)
        alerts = []

        for event in events:
            if event.id in self._t60_alerted:
                continue
            if event.impact not in ("HIGH", "MEDIUM"):
                continue
            if not event.relevant_symbols:
                continue

            minutes_until = (event.scheduled_at_utc - now).total_seconds() / 60.0
            if minutes_until < 0 or minutes_until > self.t60_minutes + 1:
                continue

            alert = CalendarAlert(
                alert_type="t60_block",
                event_title=event.title,
                event_id=event.id,
                scheduled_at_utc=event.scheduled_at_utc,
                impact=event.impact,
                category=event.category,
                relevant_symbols=event.relevant_symbols or [],
                minutes_until=minutes_until,
                forecast=event.forecast,
                previous=event.previous,
            )
            alerts.append(alert)
            self._t60_alerted.add(event.id)

            # Activate risk window
            news_risk_window.activate_t60(
                event_id=event.id,
                event_title=event.title,
                scheduled_at_utc=event.scheduled_at_utc,
                impact=event.impact,
                category=event.category,
                relevant_symbols=event.relevant_symbols or [],
                forecast=event.forecast,
                previous=event.previous,
            )

        return alerts

    # ── T-30 Alerts ──────────────────────────────────────────────

    async def check_t30_alerts(self, now: Optional[datetime] = None) -> List[CalendarAlert]:
        """Find HIGH/MEDIUM events at T-30."""
        now = now or datetime.now(timezone.utc)
        window_start = now + timedelta(minutes=self.t30_minutes - 1)
        window_end = now + timedelta(minutes=self.t30_minutes + 1)

        events = await self._query_events_in_window(window_start, window_end)
        alerts = []

        for event in events:
            if event.id in self._t30_alerted:
                continue
            if event.impact not in ("HIGH", "MEDIUM"):
                continue
            if not event.relevant_symbols:
                continue

            minutes_until = (event.scheduled_at_utc - now).total_seconds() / 60.0

            alert = CalendarAlert(
                alert_type="t30_alert",
                event_title=event.title,
                event_id=event.id,
                scheduled_at_utc=event.scheduled_at_utc,
                impact=event.impact,
                category=event.category,
                relevant_symbols=event.relevant_symbols or [],
                minutes_until=minutes_until,
                forecast=event.forecast,
                previous=event.previous,
            )
            alerts.append(alert)
            self._t30_alerted.add(event.id)

        return alerts

    # ── T-5 Alerts ───────────────────────────────────────────────

    async def check_t5_alerts(self, now: Optional[datetime] = None) -> List[CalendarAlert]:
        """Find HIGH events at T-5."""
        now = now or datetime.now(timezone.utc)
        window_start = now + timedelta(minutes=self.t5_minutes - 1)
        window_end = now + timedelta(minutes=self.t5_minutes + 1)

        events = await self._query_events_in_window(window_start, window_end)
        alerts = []

        for event in events:
            if event.id in self._t5_alerted:
                continue
            if event.impact != "HIGH":
                continue
            if not event.relevant_symbols:
                continue

            minutes_until = (event.scheduled_at_utc - now).total_seconds() / 60.0

            alert = CalendarAlert(
                alert_type="t5_alert",
                event_title=event.title,
                event_id=event.id,
                scheduled_at_utc=event.scheduled_at_utc,
                impact=event.impact,
                category=event.category,
                relevant_symbols=event.relevant_symbols or [],
                minutes_until=minutes_until,
                forecast=event.forecast,
                previous=event.previous,
            )
            alerts.append(alert)
            self._t5_alerted.add(event.id)

        return alerts

    # ── Actual Release ───────────────────────────────────────────

    async def check_actual_release(self, now: Optional[datetime] = None) -> List[CalendarAlert]:
        """Find events that just released their actual value."""
        now = now or datetime.now(timezone.utc)
        # Check events from the last 2 hours that are now RELEASED
        window_start = now - timedelta(hours=2)
        window_end = now + timedelta(minutes=5)

        async with async_session_factory() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(CalendarEvent).where(
                    CalendarEvent.scheduled_at_utc >= window_start,
                    CalendarEvent.scheduled_at_utc <= window_end,
                    CalendarEvent.status == "RELEASED",
                    CalendarEvent.actual.isnot(None),
                )
            )
            events = result.scalars().all()

        alerts = []
        for event in events:
            if event.id in self._released_emitted:
                continue
            if not event.relevant_symbols:
                continue

            alert = CalendarAlert(
                alert_type="released",
                event_title=event.title,
                event_id=event.id,
                scheduled_at_utc=event.scheduled_at_utc,
                impact=event.impact,
                category=event.category,
                relevant_symbols=event.relevant_symbols or [],
                minutes_until=0,
                forecast=event.forecast,
                previous=event.previous,
                actual=event.actual,
                surprise=event.surprise,
            )
            alerts.append(alert)
            self._released_emitted.add(event.id)

            # Update risk window state
            news_risk_window.activate_release(
                event_id=event.id,
                actual=event.actual,
                surprise=event.surprise,
            )

        return alerts

    # ── Weekly Summary ───────────────────────────────────────────

    async def generate_weekly_summary(
        self, week_start: Optional[datetime] = None,
    ) -> Optional[WeeklySummary]:
        """Generate a weekly calendar summary for the current or given week."""
        now = datetime.now(timezone.utc)
        if week_start is None:
            # Monday of this week
            week_start = now - timedelta(days=now.weekday())
            week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)

        week_end = week_start + timedelta(days=7)

        async with async_session_factory() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(CalendarEvent).where(
                    CalendarEvent.scheduled_at_utc >= week_start,
                    CalendarEvent.scheduled_at_utc < week_end,
                    CalendarEvent.country == "US",
                ).order_by(CalendarEvent.scheduled_at_utc)
            )
            events = result.scalars().all()

        if not events:
            return None

        high = sum(1 for e in events if e.impact == "HIGH")
        medium = sum(1 for e in events if e.impact == "MEDIUM")
        low = sum(1 for e in events if e.impact == "LOW")

        top = [e.to_dict() for e in events if e.impact in ("HIGH", "MEDIUM")]

        return WeeklySummary(
            week_start=week_start,
            week_end=week_end,
            total_events=len(events),
            high_impact_count=high,
            medium_impact_count=medium,
            low_impact_count=low,
            events=[e.to_dict() for e in events],
            top_events=top,
        )

    # ── EventBus emitters ────────────────────────────────────────

    def _emit_t60(self, alert: CalendarAlert) -> None:
        event_bus.publish(EventType.CALENDAR_T60_ALERT.value, {
            "event_type": EventType.CALENDAR_T60_ALERT.value,
            "data": alert.to_dict(),
            "message": f"T-60: {alert.event_title} in {int(alert.minutes_until)} min",
        })
        logger.info(
            "EMIT CALENDAR_T60: %s in %d min (impact=%s, symbols=%s)",
            alert.event_title, int(alert.minutes_until),
            alert.impact, alert.relevant_symbols,
        )

    def _emit_t30(self, alert: CalendarAlert) -> None:
        event_bus.publish(EventType.CALENDAR_T30_ALERT.value, {
            "event_type": EventType.CALENDAR_T30_ALERT.value,
            "data": alert.to_dict(),
            "message": f"T-30: {alert.event_title} in {int(alert.minutes_until)} min",
        })
        logger.info(
            "EMIT CALENDAR_T30: %s in %d min",
            alert.event_title, int(alert.minutes_until),
        )

    def _emit_t5(self, alert: CalendarAlert) -> None:
        event_bus.publish(EventType.CALENDAR_T5_ALERT.value, {
            "event_type": EventType.CALENDAR_T5_ALERT.value,
            "data": alert.to_dict(),
            "message": f"T-5: {alert.event_title} in {int(alert.minutes_until)} min",
        })
        logger.info(
            "EMIT CALENDAR_T5: %s in %d min",
            alert.event_title, int(alert.minutes_until),
        )

    def _emit_released(self, alert: CalendarAlert) -> None:
        event_bus.publish(EventType.ECONOMIC_EVENT_RELEASED.value, {
            "event_type": EventType.ECONOMIC_EVENT_RELEASED.value,
            "data": alert.to_dict(),
            "message": f"RELEASED: {alert.event_title} = {alert.actual}",
        })
        logger.info(
            "EMIT ECONOMIC_EVENT_RELEASED: %s = %s (surprise=%s)",
            alert.event_title, alert.actual, alert.surprise,
        )

    def _emit_weekly(self, summary: WeeklySummary) -> None:
        self._weekly_sent = datetime.now(timezone.utc)
        event_bus.publish(EventType.CALENDAR_WEEKLY_SUMMARY.value, {
            "event_type": EventType.CALENDAR_WEEKLY_SUMMARY.value,
            "data": summary.to_dict(),
            "message": f"Weekly calendar: {summary.total_events} events, {summary.high_impact_count} HIGH",
        })
        logger.info(
            "EMIT CALENDAR_WEEKLY: %d events (%d HIGH, %d MED, %d LOW)",
            summary.total_events, summary.high_impact_count,
            summary.medium_impact_count, summary.low_impact_count,
        )

    # ── Reaction window check ────────────────────────────────────

    def _check_reaction_windows(self, now: datetime) -> None:
        """Transition released events to reaction window after cooldown."""
        for event in list(news_risk_window.get_active_events()):
            if event.released_at is None:
                continue
            minutes_since = (now - event.released_at).total_seconds() / 60.0
            if minutes_since >= self.reaction_window_minutes:
                news_risk_window.activate_reaction_window(event.event_id)
            # After reaction window, deactivate
            if minutes_since >= self.reaction_window_minutes + 5:
                news_risk_window.deactivate(event.event_id)

    # ── Helpers ──────────────────────────────────────────────────

    async def _query_events_in_window(
        self, start: datetime, end: datetime
    ) -> List[CalendarEvent]:
        """Query calendar_events for SCHEDULED events in a time window."""
        from sqlalchemy import select
        async with async_session_factory() as session:
            result = await session.execute(
                select(CalendarEvent).where(
                    CalendarEvent.scheduled_at_utc >= start,
                    CalendarEvent.scheduled_at_utc <= end,
                    CalendarEvent.status.in_(["SCHEDULED", "REVISED"]),
                    CalendarEvent.country == "US",
                )
            )
            return list(result.scalars().all())

    def _should_send_weekly(self, now: datetime) -> bool:
        """Check if we should send the weekly summary this Monday."""
        if self._weekly_sent is None:
            return True
        # Don't send if we already sent this week
        this_monday = now - timedelta(days=now.weekday())
        this_monday = this_monday.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
        return self._weekly_sent < this_monday


# ── Module-level singleton ──────────────────────────────────────
production_calendar_scheduler = ProductionCalendarScheduler()

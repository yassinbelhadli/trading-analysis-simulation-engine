"""EconomicCalendarService — single source of truth for US economic events.

Responsibilities:
  - Fetch from multiple sources (Investing.com, BLS, BEA, Fed)
  - Normalize to EconomicEvent model
  - Upsert into calendar_events table (idempotent)
  - Deduplicate by (source, external_id)
  - Publish EventBus events on changes
  - Track data quality / staleness

The service does NOT:
  - Make trading decisions
  - Block or allow trades
  - Send Telegram messages directly

Those responsibilities belong to Phase 3 consumers.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core_engine.events.event_bus import event_bus
from core_engine.events.event_types import EventType
from database.calendar_models import CalendarEvent
from database.db import async_session_factory
from economic_calendar.impact import ImpactClassifier
from economic_calendar.models import EconomicEvent
from economic_calendar.relevance import MarketRelevanceMapper
from economic_calendar.sources.base import CalendarSource
from economic_calendar.sources.forexfactory import ForexFactorySource
from economic_calendar.staleness import DataQuality, StalenessPolicy

logger = logging.getLogger(__name__)


class EconomicCalendarService:
    """Single source of truth for US economic calendar events.

    Usage::

        service = EconomicCalendarService()
        await service.start()
        events = await service.get_upcoming(hours=48)
        await service.stop()
    """

    def __init__(
        self,
        sources: Optional[List[CalendarSource]] = None,
        impact_classifier: Optional[ImpactClassifier] = None,
        relevance_mapper: Optional[MarketRelevanceMapper] = None,
        staleness_policy: Optional[StalenessPolicy] = None,
    ):
        # Only ForexFactory XML — Investing.com (403) and BLS (404) are broken
        self.sources = sources or [ForexFactorySource()]
        self.impact_classifier = impact_classifier or ImpactClassifier()
        self.relevance_mapper = relevance_mapper or MarketRelevanceMapper()
        self.staleness_policy = staleness_policy or StalenessPolicy()

        self._running = False
        self._fetch_interval_minutes = 60  # how often to re-fetch

    # ── Lifecycle ────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the calendar service."""
        if self._running:
            return
        self._running = True
        logger.info("EconomicCalendarService started")

    async def stop(self) -> None:
        """Stop the calendar service."""
        self._running = False
        logger.info("EconomicCalendarService stopped")

    # ── Fetch + Upsert ──────────────────────────────────────────

    async def fetch_and_upsert(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, int]:
        """Fetch from all sources, normalize, and upsert into DB.

        Returns:
            Dict with counts: {created, updated, unchanged, errors}
        """
        stats = {"created": 0, "updated": 0, "unchanged": 0, "errors": 0}

        for source in self.sources:
            try:
                raw_events = await source.fetch(start_date, end_date)
                logger.info(
                    "Fetched %d events from %s",
                    len(raw_events), source.source_name,
                )
            except Exception as e:
                logger.error("Fetch failed from %s: %s", source.source_name, e)
                await self._mark_source_failure(source.source_name)
                stats["errors"] += 1
                continue

            for event in raw_events:
                try:
                    # Enrich with impact classification
                    classified = self.impact_classifier.classify(event.title)
                    event.impact = classified.impact
                    event.category = classified.category

                    # Enrich with market relevance
                    event.relevant_symbols = self.relevance_mapper.get_relevant_symbols(event.title)

                    result = await self._upsert_event(event)
                    stats[result] += 1
                except Exception as e:
                    logger.error("Upsert failed for %s: %s", event.title, e)
                    stats["errors"] += 1

            # Mark source as successful
            await self._mark_source_success(source.source_name)

        # Publish CALENDAR_UPDATED if any changes
        if stats["created"] > 0 or stats["updated"] > 0:
            self._publish_calendar_updated(stats)

        logger.info("Fetch+upsert complete: %s", stats)
        return stats

    async def _upsert_event(self, event: EconomicEvent) -> str:
        """Upsert a single event into the DB. Returns 'created', 'updated', or 'unchanged'."""
        async with async_session_factory() as session:
            # Check existing
            existing = await session.execute(
                select(CalendarEvent).where(
                    CalendarEvent.source == event.source,
                    CalendarEvent.external_id == event.external_id,
                )
            )
            existing_event = existing.scalar_one_or_none()

            now = datetime.now(timezone.utc)

            if existing_event is None:
                # CREATE
                new_event = CalendarEvent(
                    source=event.source,
                    external_id=event.external_id,
                    country=event.country,
                    currency=event.currency,
                    title=event.title,
                    description=event.description,
                    category=event.category,
                    impact=event.impact,
                    scheduled_at_utc=event.scheduled_at,
                    scheduled_at_et=self._utc_to_et(event.scheduled_at),
                    forecast=event.forecast,
                    previous=event.previous,
                    actual=event.actual,
                    surprise=self._calc_surprise(event.forecast, event.actual),
                    status=event.status,
                    relevant_symbols=event.relevant_symbols,
                    source_url=event.source_url,
                    fetched_at=now,
                    data_quality="FRESH",
                )
                session.add(new_event)
                await session.commit()

                self._publish_event_created(new_event)
                return "created"

            # UPDATE — only if data changed
            changed = False

            if event.actual is not None and existing_event.actual != event.actual:
                existing_event.actual = event.actual
                existing_event.actual_released_at = now
                existing_event.status = "RELEASED"
                changed = True

            if event.forecast is not None and existing_event.forecast != event.forecast:
                existing_event.forecast = event.forecast
                changed = True

            if event.previous is not None and existing_event.previous != event.previous:
                existing_event.previous = event.previous
                changed = True

            if event.status != existing_event.status:
                existing_event.status = event.status
                changed = True

            # Always update impact/category/relevance (may have been enriched)
            if existing_event.impact != event.impact:
                existing_event.impact = event.impact
                changed = True
            if existing_event.category != event.category:
                existing_event.category = event.category
                changed = True

            # Recalculate surprise
            new_surprise = self._calc_surprise(
                event.forecast or existing_event.forecast,
                event.actual or existing_event.actual,
            )
            if existing_event.surprise != new_surprise:
                existing_event.surprise = new_surprise
                changed = True

            existing_event.fetched_at = now

            if changed:
                existing_event.updated_at = now
                await session.commit()
                self._publish_event_updated(existing_event)
                return "updated"

            await session.commit()
            return "unchanged"

    # ── Read methods ─────────────────────────────────────────────

    async def get_upcoming(
        self,
        hours: int = 48,
        impact_filter: Optional[str] = None,
        symbol_filter: Optional[str] = None,
    ) -> List[Dict]:
        """Get upcoming events within the next N hours.

        Args:
            hours: Look-ahead window in hours.
            impact_filter: Only return events with this impact level.
            symbol_filter: Only return events relevant to this symbol.

        Returns:
            List of event dicts sorted by scheduled_at_utc.
        """
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(hours=hours)

        async with async_session_factory() as session:
            query = select(CalendarEvent).where(
                CalendarEvent.scheduled_at_utc >= now,
                CalendarEvent.scheduled_at_utc <= cutoff,
                CalendarEvent.status.in_(["SCHEDULED", "REVISED"]),
            )
            if impact_filter:
                query = query.where(CalendarEvent.impact == impact_filter)

            query = query.order_by(CalendarEvent.scheduled_at_utc)

            result = await session.execute(query)
            events = result.scalars().all()

            # Filter by symbol if requested
            if symbol_filter:
                events = [
                    e for e in events
                    if symbol_filter in (e.relevant_symbols or [])
                ]

            return [e.to_dict() for e in events]

    async def get_event_by_id(self, event_id: str) -> Optional[Dict]:
        """Get a single event by DB ID."""
        async with async_session_factory() as session:
            result = await session.execute(
                select(CalendarEvent).where(CalendarEvent.id == event_id)
            )
            event = result.scalar_one_or_none()
            return event.to_dict() if event else None

    async def get_events_in_window(
        self,
        start_utc: datetime,
        end_utc: datetime,
        impact_filter: Optional[str] = None,
    ) -> List[Dict]:
        """Get events in a specific UTC time window.

        Used by Phase 3 for T-60/T-30/T-5 protection and notifications.
        """
        async with async_session_factory() as session:
            query = select(CalendarEvent).where(
                CalendarEvent.scheduled_at_utc >= start_utc,
                CalendarEvent.scheduled_at_utc <= end_utc,
            )
            if impact_filter:
                query = query.where(CalendarEvent.impact == impact_filter)
            query = query.order_by(CalendarEvent.scheduled_at_utc)

            result = await session.execute(query)
            return [e.to_dict() for e in result.scalars().all()]

    async def get_data_quality(self) -> Dict[str, str]:
        """Return data quality status per source.

        Returns:
            Dict mapping source_name → DataQuality string.
        """
        qualities: Dict[str, str] = {}

        async with async_session_factory() as session:
            # Get latest event per source
            for source_name in ["forexfactory", "investing_com", "bls", "bea", "federal_reserve"]:
                result = await session.execute(
                    select(CalendarEvent)
                    .where(CalendarEvent.source == source_name)
                    .order_by(CalendarEvent.fetched_at.desc())
                    .limit(1)
                )
                latest = result.scalar_one_or_none()

                if latest is None:
                    qualities[source_name] = DataQuality.UNAVAILABLE.value
                    continue

                quality = self.staleness_policy.evaluate(
                    last_success_at=latest.fetched_at,
                    consecutive_failures=latest.consecutive_failures,
                )
                qualities[source_name] = quality.value

        return qualities

    # ── Private helpers ──────────────────────────────────────────

    async def _mark_source_failure(self, source_name: str) -> None:
        """Increment consecutive_failures for all events from this source."""
        async with async_session_factory() as session:
            await session.execute(
                update(CalendarEvent)
                .where(CalendarEvent.source == source_name)
                .values(
                    consecutive_failures=CalendarEvent.consecutive_failures + 1,
                    data_quality="STALE",
                )
            )
            await session.commit()

    async def _mark_source_success(self, source_name: str) -> None:
        """Reset consecutive_failures for events from this source."""
        async with async_session_factory() as session:
            await session.execute(
                update(CalendarEvent)
                .where(CalendarEvent.source == source_name)
                .values(
                    consecutive_failures=0,
                    data_quality="FRESH",
                )
            )
            await session.commit()

    @staticmethod
    def _calc_surprise(
        forecast: Optional[float], actual: Optional[float]
    ) -> Optional[float]:
        """Calculate surprise = actual - forecast."""
        if forecast is None or actual is None:
            return None
        return round(actual - forecast, 4)

    @staticmethod
    def _utc_to_et(utc_dt: datetime) -> Optional[datetime]:
        """Convert UTC datetime to Eastern Time.

        Uses fixed UTC-5/UTC-4 offset. For production, use zoneinfo.
        """
        try:
            from zoneinfo import ZoneInfo
            et = utc_dt.astimezone(ZoneInfo("America/New_York"))
            return et
        except ImportError:
            # Fallback: rough EDT/EST approximation
            offset = timedelta(hours=-4)  # EDT
            return utc_dt + offset

    # ── EventBus publishers ──────────────────────────────────────

    def _publish_calendar_updated(self, stats: Dict[str, int]) -> None:
        event_bus.publish(
            EventType.CALENDAR_UPDATED.value,
            {
                "event_type": EventType.CALENDAR_UPDATED.value,
                "data": stats,
                "message": f"Calendar updated: {stats}",
            },
        )

    def _publish_event_created(self, db_event: CalendarEvent) -> None:
        event_bus.publish(
            EventType.ECONOMIC_EVENT_CREATED.value,
            {
                "event_type": EventType.ECONOMIC_EVENT_CREATED.value,
                "data": db_event.to_dict(),
                "message": f"New economic event: {db_event.title}",
            },
        )

    def _publish_event_updated(self, db_event: CalendarEvent) -> None:
        event_bus.publish(
            EventType.ECONOMIC_EVENT_UPDATED.value,
            {
                "event_type": EventType.ECONOMIC_EVENT_UPDATED.value,
                "data": db_event.to_dict(),
                "message": f"Economic event updated: {db_event.title}",
            },
        )

    def _publish_event_released(self, db_event: CalendarEvent) -> None:
        event_bus.publish(
            EventType.ECONOMIC_EVENT_RELEASED.value,
            {
                "event_type": EventType.ECONOMIC_EVENT_RELEASED.value,
                "data": db_event.to_dict(),
                "message": f"Economic event released: {db_event.title} = {db_event.actual}",
            },
        )


# ── Module-level singleton ────────────────────────────────────────
economic_calendar_service = EconomicCalendarService()

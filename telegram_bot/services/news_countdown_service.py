"""NewsCountdownService — monitors upcoming high-impact events
and publishes NEWS_COUNTDOWN events at 60, 30, 15, 5, 0 minutes."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from core_engine.events.event_bus import event_bus
from core_engine.events.event_types import EventType

logger = logging.getLogger(__name__)

_COUNTDOWN_INTERVALS = [60, 30, 15, 5, 0]


class NewsCountdownService:
    """Publishes NEWS_COUNTDOWN events at strategic intervals before high-impact news."""

    def __init__(self, check_interval: float = 30.0):
        self.check_interval = check_interval
        self._task: asyncio.Task | None = None
        self._running = False
        self._alerted_events: dict[str, set[int]] = {}

    def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run())
        logger.info("NewsCountdownService started")

    def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("NewsCountdownService stopped")

    async def _run(self):
        while self._running:
            try:
                await self._check_upcoming()
            except Exception as e:
                logger.error("NewsCountdown check failed: %s", e)
            await asyncio.sleep(self.check_interval)

    async def _check_upcoming(self):
        now = datetime.now(timezone.utc)
        from database.db import async_session_factory
        from sqlalchemy import select
        from database.models import NewsEvent

        window_end = now + timedelta(hours=2)
        async with async_session_factory() as session:
            result = await session.execute(
                select(NewsEvent).where(
                    NewsEvent.currency == "USD",
                    NewsEvent.impact == "HIGH",
                    NewsEvent.time >= now,
                    NewsEvent.time <= window_end,
                ).order_by(NewsEvent.time)
            )
            events = result.scalars().all()

        for ev in events:
            if not ev.time:
                continue
            mins_until = (ev.time - now).total_seconds() / 60.0
            for interval in _COUNTDOWN_INTERVALS:
                if mins_until <= interval and interval not in self._alerted_events.setdefault(ev.news_id, set()):
                    self._alerted_events[ev.news_id].add(interval)
                    event_bus.publish(EventType.NEWS_COUNTDOWN.value, {
                        "event_type": EventType.NEWS_COUNTDOWN.value,
                        "account_id": "",
                        "user_id": "",
                        "trade_id": "",
                        "message": f"Countdown: {ev.event} in {interval} min",
                        "data": {
                            "event": ev.event,
                            "currency": ev.currency,
                            "impact": ev.impact,
                            "minutes_remaining": interval,
                            "time": ev.time.isoformat() if ev.time else "",
                        },
                        "timestamp": now.isoformat(),
                    })
                    if interval > 0:
                        logger.info("News countdown: %s in %d min", ev.event, interval)
                    else:
                        logger.info("News LIVE: %s", ev.event)

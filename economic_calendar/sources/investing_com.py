"""Investing.com calendar adapter.

Uses the Investing.com economic calendar page to fetch US economic events.
This is a web-scraping adapter — use as fallback when official API sources
(BLS, BEA, Fed) are unavailable.

Produces normalized EconomicEvent objects with source="investing_com".
"""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import httpx

from economic_calendar.models import EconomicEvent
from economic_calendar.sources.base import CalendarSource

logger = logging.getLogger(__name__)

# Investing.com calendar API endpoint (JSON)
_INVESTING_CALENDAR_URL = "https://sslecal2.investing.com/events/eventsList"

# US country ID on Investing.com
_US_COUNTRY_ID = 5

# Default headers to mimic browser
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.investing.com/economic-calendar/",
}

# Impact mapping from Investing.com numeric to our string format
_IMPACT_MAP: Dict[int, str] = {
    1: "LOW",
    2: "MEDIUM",
    3: "HIGH",
}


class InvestingComSource(CalendarSource):
    """Fetch US economic calendar from Investing.com."""

    source_name = "investing_com"

    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout

    async def fetch(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[EconomicEvent]:
        """Fetch US events from Investing.com calendar API.

        Args:
            start_date: ISO date (YYYY-MM-DD). Defaults to today.
            end_date: ISO date (YYYY-MM-DD). Defaults to today + 7 days.
        """
        now = datetime.now(timezone.utc)
        if start_date is None:
            start_date = now.strftime("%Y-%m-%d")
        if end_date is None:
            end_date = (now + timedelta(days=7)).strftime("%Y-%m-%d")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(
                    _INVESTING_CALENDAR_URL,
                    params={
                        "country[]": _US_COUNTRY_ID,
                        "dateFrom": start_date,
                        "dateTo": end_date,
                        "timeZone": "5",  # UTC
                    },
                    headers=_HEADERS,
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as e:
            logger.error("Investing.com fetch failed: %s", e)
            return []
        except Exception as e:
            logger.error("Investing.com unexpected error: %s", e)
            return []

        events: List[EconomicEvent] = []
        rows = data.get("data", []) if isinstance(data, dict) else data if isinstance(data, list) else []

        for row in rows:
            try:
                event = self._parse_event(row)
                if event:
                    events.append(event)
            except Exception as e:
                logger.debug("Failed to parse Investing.com row: %s", e)
                continue

        logger.info("Investing.com: fetched %d US events", len(events))
        return events

    async def fetch_event_detail(self, external_id: str) -> Optional[EconomicEvent]:
        """Not implemented — Investing.com doesn't expose single-event API."""
        return None

    def _parse_event(self, row: dict) -> Optional[EconomicEvent]:
        """Parse a single Investing.com calendar row into EconomicEvent."""
        title = row.get("title", "").strip()
        if not title:
            return None

        # Parse scheduled time (UTC)
        time_str = row.get("time") or row.get("date")
        if not time_str:
            return None

        scheduled_utc = self._parse_time(time_str)
        if scheduled_utc is None:
            return None

        # External ID
        event_id = str(row.get("id") or row.get("eventId") or "")
        if not event_id:
            event_id = self._make_id(title, scheduled_utc)

        # Impact
        impact_num = row.get("impact") or row.get("importance") or 1
        impact = _IMPACT_MAP.get(int(impact_num), "LOW")

        # Values
        forecast = self._safe_float(row.get("forecast") or row.get("consensus"))
        previous = self._safe_float(row.get("previous"))
        actual = self._safe_float(row.get("actual") or row.get("actualValue"))

        # Status
        status = "SCHEDULED"
        if actual is not None:
            status = "RELEASED"

        return EconomicEvent(
            source="investing_com",
            external_id=event_id,
            title=title,
            scheduled_at=scheduled_utc,
            country="US",
            currency="USD",
            impact=impact,
            forecast=forecast,
            previous=previous,
            actual=actual,
            status=status,
            source_url=f"https://www.investing.com/economic-calendar/{event_id}",
        )

    def _parse_time(self, time_str: str) -> Optional[datetime]:
        """Parse Investing.com time string to UTC datetime."""
        # Try ISO format first
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(time_str, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue
        return None

    @staticmethod
    def _safe_float(val) -> Optional[float]:
        if val is None:
            return None
        try:
            s = str(val).strip().replace(",", "").replace("%", "")
            if s in ("", "-", "N/A", "n/a"):
                return None
            return float(s)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _make_id(title: str, dt: datetime) -> str:
        raw = f"investing_com:{title}:{dt.isoformat()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

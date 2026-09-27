"""ForexFactory calendar adapter — XML endpoint.

Uses the community-maintained ForexFactory XML mirror at
nfs.faireconomy.media.  The JSON endpoint is unreliable (429 rate limits,
404 on next week).  The XML endpoint is proven stable.

Source: https://nfs.faireconomy.media/ff_calendar_thisweek.xml
        https://nfs.faireconomy.media/ff_calendar_nextweek.xml

The XML feed publishes times in Eastern Time and includes ALL currencies.
We filter to US/USD events only and convert all times to UTC.

Data shape per <event>:
    <title>FOMC Statement</title>
    <country>USD</country>
    <date>Tue Aug 19</date>
    <time>2:00pm</time>
    <impact>High</impact>
    <forecast>0.25%</forecast>
    <previous>0.25%</previous>
    <actual>0.50%</actual>
"""
from __future__ import annotations

import hashlib
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import httpx

from economic_calendar.models import EconomicEvent
from economic_calendar.sources.base import CalendarSource

logger = logging.getLogger(__name__)

# ForexFactory community mirror XML endpoints
_FF_THIS_WEEK_XML = "https://nfs.faireconomy.media/ff_calendar_thisweek.xml"
_FF_NEXT_WEEK_XML = "https://nfs.faireconomy.media/ff_calendar_nextweek.xml"

# Only keep US dollar events
_US_COUNTRIES = {"USD"}

# Impact mapping
_IMPACT_MAP: Dict[str, str] = {
    "High": "HIGH",
    "Medium": "MEDIUM",
    "Low": "LOW",
    "holiday": "LOW",
    "Holiday": "LOW",
}

# Eastern Time zone
try:
    from zoneinfo import ZoneInfo
    _ET = ZoneInfo("America/New_York")
except ImportError:
    _ET = None


class ForexFactorySource(CalendarSource):
    """Fetch US economic calendar from ForexFactory community XML mirror.

    This is the primary source — proven working, provides forecast/previous
    values, and handles rate limiting gracefully.
    """

    source_name = "forexfactory"

    def __init__(self, timeout: float = 30.0, us_only: bool = True):
        self.timeout = timeout
        self.us_only = us_only

    async def fetch(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[EconomicEvent]:
        """Fetch US events from ForexFactory XML feed.

        Fetches both this-week and next-week endpoints to cover the
        requested date range.
        """
        now = datetime.now(timezone.utc)
        if start_date is None:
            start_date = now.strftime("%Y-%m-%d")
        if end_date is None:
            end_date = (now + timedelta(days=7)).strftime("%Y-%m-%d")

        sd = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        ed = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)

        all_events: List[EconomicEvent] = []

        for url in [_FF_THIS_WEEK_XML, _FF_NEXT_WEEK_XML]:
            try:
                events = await self._fetch_xml(url, sd, ed)
                all_events.extend(events)
            except Exception as e:
                logger.warning("ForexFactory XML fetch failed from %s: %s", url, e)
                continue

        # Deduplicate by external_id
        seen: set = set()
        deduped: List[EconomicEvent] = []
        for event in all_events:
            if event.external_id not in seen:
                seen.add(event.external_id)
                deduped.append(event)

        logger.info(
            "ForexFactory XML: fetched %d US events (deduped from %d)",
            len(deduped), len(all_events),
        )
        return deduped

    async def fetch_event_detail(self, external_id: str) -> Optional[EconomicEvent]:
        """Not implemented — ForexFactory doesn't expose single-event API."""
        return None

    async def _fetch_xml(
        self, url: str, sd: datetime, ed: datetime
    ) -> List[EconomicEvent]:
        """Fetch a single ForexFactory XML endpoint and parse events."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/125.0.0.0 Safari/537.36"
                    ),
                },
            )
            resp.raise_for_status()

        root = ET.fromstring(resp.content)

        events: List[EconomicEvent] = []
        for item in root.findall(".//event"):
            event = self._parse_xml_event(item, sd, ed)
            if event:
                events.append(event)

        return events

    def _parse_xml_event(
        self, item: ET.Element, sd: datetime, ed: datetime
    ) -> Optional[EconomicEvent]:
        """Parse a single XML <event> into EconomicEvent."""
        title = self._text(item, "title")
        country = self._text(item, "country")
        date_text = self._text(item, "date")
        time_text = self._text(item, "time")
        impact_raw = self._text(item, "impact")
        forecast_text = self._text(item, "forecast")
        previous_text = self._text(item, "previous")
        actual_text = self._text(item, "actual")
        url_text = self._text(item, "url")

        if not title or not date_text:
            return None

        # Country filter
        if self.us_only and country not in _US_COUNTRIES:
            return None

        # Parse datetime (ET → UTC)
        scheduled_utc = self._parse_datetime(date_text, time_text)
        if scheduled_utc is None:
            return None

        # Date range filter
        if scheduled_utc < sd or scheduled_utc > ed:
            return None

        impact = _IMPACT_MAP.get(impact_raw, "LOW")
        forecast = self._safe_float(forecast_text)
        previous = self._safe_float(previous_text)
        actual = self._safe_float(actual_text)

        # External ID from URL slug or deterministic hash
        external_id = self._make_external_id(url_text, title, scheduled_utc)

        # Status
        status = "RELEASED" if actual is not None else "SCHEDULED"

        return EconomicEvent(
            source="forexfactory",
            external_id=external_id,
            title=title,
            scheduled_at=scheduled_utc,
            country="US",
            currency="USD",
            impact=impact,
            forecast=forecast,
            previous=previous,
            actual=actual,
            status=status,
            source_url=url_text or "https://www.forexfactory.com/calendar",
        )

    def _parse_datetime(self, date_text: str, time_text: str) -> Optional[datetime]:
        """Parse ForexFactory date+time to UTC.

        Format examples: "Tue Aug 19", "2:00pm", "All Day", "Tentative"
        """
        raw = f"{date_text} {time_text}".strip()
        raw = (
            raw.replace("All Day", "00:00")
            .replace("Tentative", "00:00")
            .replace("Day 1", "00:00")
            .replace("Day 2", "00:00")
        )

        try:
            import pandas as pd
            parsed = pd.to_datetime(raw, errors="coerce")
        except ImportError:
            # Fallback without pandas
            for fmt in (
                "%a %b %d %I:%M%p",
                "%a %b %d %H:%M",
                "%a %b %d",
            ):
                try:
                    parsed = datetime.strptime(raw, fmt)
                    break
                except ValueError:
                    continue
            else:
                return None
            parsed = parsed.replace(tzinfo=None)
            if _ET:
                parsed = parsed.replace(tzinfo=_ET)
            return parsed.astimezone(timezone.utc)
        except Exception:
            return None

        if hasattr(parsed, "tzinfo") and parsed.tzinfo is None:
            if _ET:
                parsed = parsed.tz_localize(_ET)
            else:
                parsed = parsed.tz_localize(timezone.utc)

        if hasattr(parsed, "tz_convert"):
            parsed = parsed.tz_convert("UTC")

        return parsed.to_pydatetime() if hasattr(parsed, "to_pydatetime") else parsed

    @staticmethod
    def _text(item: ET.Element, tag: str) -> str:
        node = item.find(tag)
        if node is None or node.text is None:
            return ""
        return str(node.text).strip()

    @staticmethod
    def _safe_float(val) -> Optional[float]:
        """Parse numeric value with optional units (%, K, M, B)."""
        if val is None:
            return None
        s = str(val).strip()
        if s in ("", "-", "N/A", "n/a"):
            return None

        s = s.replace(",", "")
        multiplier = 1.0
        if s.endswith("K"):
            multiplier = 1_000
            s = s[:-1]
        elif s.endswith("M"):
            multiplier = 1_000_000
            s = s[:-1]
        elif s.endswith("B"):
            multiplier = 1_000_000_000
            s = s[:-1]
        elif s.endswith("%"):
            s = s[:-1]

        try:
            return float(s) * multiplier
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _make_external_id(url: str, title: str, dt: datetime) -> str:
        """Stable ID: ForexFactory slug from URL, else deterministic hash."""
        if url:
            last = url.rstrip("/").split("/")[-1]
            if last and last.lower() not in ("calendar",):
                return last

        raw = f"forexfactory:{title}:{dt.isoformat()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

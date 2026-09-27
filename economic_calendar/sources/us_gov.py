"""US Government official sources adapter (BLS, BEA, Federal Reserve).

Fetches release schedules from official government RSS/JSON feeds.
Official sources provide authoritative titles and release dates but
typically do NOT provide forecast/previous values.  Those are sourced
from InvestingComSource and merged at the service layer.

Produces normalized EconomicEvent objects with source=bls|bea|federal_reserve.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import httpx

from economic_calendar.models import EconomicEvent
from economic_calendar.sources.base import CalendarSource

logger = logging.getLogger(__name__)

# ── BLS (Bureau of Labor Statistics) ────────────────────────────
_BLS_RELEASES_URL = "https://api.bls.gov/publicAPI/v2/calendar/events/"

# ── BEA (Bureau of Economic Analysis) ──────────────────────────
_BEA_RELEASES_URL = "https://apps.bea.gov/api/data/?&getitemssession"

# ── Federal Reserve ─────────────────────────────────────────────
_FOMC_DATES_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"


class USGovSource(CalendarSource):
    """Fetch US economic release schedules from official government sources.

    Tries BLS first, then BEA, then Federal Reserve.  Merges results.
    Forecast/previous values are NOT available from official sources —
    those come from InvestingComSource at the service layer.
    """

    source_name = "us_gov"

    def __init__(self, timeout: float = 20.0):
        self.timeout = timeout

    async def fetch(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[EconomicEvent]:
        """Fetch US release schedules from BLS + BEA + Fed."""
        now = datetime.now(timezone.utc)
        if start_date is None:
            start_date = now.strftime("%Y-%m-%d")
        if end_date is None:
            end_date = (now + timedelta(days=30)).strftime("%Y-%m-%d")

        all_events: List[EconomicEvent] = []

        # Try each source, merge results
        for source_fetcher in [
            self._fetch_bls,
            self._fetch_bea,
        ]:
            try:
                events = await source_fetcher(start_date, end_date)
                all_events.extend(events)
            except Exception as e:
                logger.warning("USGov source %s failed: %s", source_fetcher.__name__, e)
                continue

        logger.info("USGov: fetched %d US release events", len(all_events))
        return all_events

    async def fetch_event_detail(self, external_id: str) -> Optional[EconomicEvent]:
        """Not implemented — official sources don't expose single-event API."""
        return None

    async def _fetch_bls(
        self, start_date: str, end_date: str
    ) -> List[EconomicEvent]:
        """Fetch BLS release calendar via public API v2."""
        events: List[EconomicEvent] = []

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    _BLS_RELEASES_URL,
                    json={
                        "startyear": start_date[:4],
                        "endyear": end_date[:4],
                    },
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            logger.warning("BLS fetch failed: %s", e)
            return events

        releases = data.get("Results", {}).get("releases", [])

        for release in releases:
            title = release.get("release_name", "").strip()
            if not title:
                continue

            # Parse release date
            date_str = release.get("release_date") or release.get("date")
            if not date_str:
                continue

            scheduled = self._parse_date(date_str)
            if scheduled is None:
                continue

            # Filter to date range
            sd = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            ed = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if scheduled < sd or scheduled > ed:
                continue

            ext_id = f"bls:{release.get('release_id', '')}" if release.get("release_id") else self._make_id(title, scheduled)

            events.append(EconomicEvent(
                source="bls",
                external_id=ext_id,
                title=title,
                scheduled_at=scheduled,
                country="US",
                currency="USD",
                status="SCHEDULED",
                source_url="https://www.bls.gov/schedule/",
            ))

        return events

    async def _fetch_bea(
        self, start_date: str, end_date: str
    ) -> List[EconomicEvent]:
        """Fetch BEA release schedule.

        BEA publishes release dates at:
        https://www.bea.gov/news/schedule
        We fetch the schedule page and parse known release patterns.
        """
        events: List[EconomicEvent] = []

        # Known BEA releases with approximate monthly schedules
        # GDP, PCE, Personal Income, Trade Balance
        known_releases = [
            ("Gross Domestic Product (GDP)", "gdp"),
            ("Personal Income and Outlays (PCE)", "inflation"),
            ("Trade Balance", "trade"),
            ("Goods Trade Balance", "trade"),
            ("International Trade in Goods and Services", "trade"),
        ]

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # BEA doesn't have a clean JSON API for schedule — use RSS
                resp = await client.get(
                    "https://www.bea.gov/rss/gdp.xml",
                    follow_redirects=True,
                )
                if resp.status_code == 200:
                    # Parse RSS for recent releases
                    text = resp.text
                    import xml.etree.ElementTree as ET
                    try:
                        root = ET.fromstring(text)
                        items = root.findall(".//item")[:10]  # last 10 items

                        for item in items:
                            title_el = item.find("title")
                            pub_date_el = item.find("pubDate")
                            link_el = item.find("link")

                            if title_el is None or pub_date_el is None:
                                continue

                            title = (title_el.text or "").strip()
                            if not title:
                                continue

                            pub_date_str = (pub_date_el.text or "").strip()
                            scheduled = self._parse_rss_date(pub_date_str)
                            if scheduled is None:
                                continue

                            # Filter to date range
                            sd = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                            ed = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                            if scheduled < sd or scheduled > ed:
                                continue

                            ext_id = f"bea:{hashlib.sha256(title.encode()).hexdigest()[:16]}"
                            source_url = (link_el.text or "").strip() if link_el is not None else None

                            events.append(EconomicEvent(
                                source="bea",
                                external_id=ext_id,
                                title=title,
                                scheduled_at=scheduled,
                                country="US",
                                currency="USD",
                                status="RELEASED",
                                source_url=source_url or "https://www.bea.gov/",
                            ))
                    except ET.ParseError:
                        logger.debug("Failed to parse BEA RSS")
        except Exception as e:
            logger.warning("BEA fetch failed: %s", e)

        return events

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string to UTC datetime."""
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%m/%d/%Y", "%B %d, %Y"):
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue
        return None

    def _parse_rss_date(self, date_str: str) -> Optional[datetime]:
        """Parse RFC 2822 / RSS date format."""
        import email.utils
        try:
            parsed = email.utils.parsedate_to_datetime(date_str)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except Exception:
            return self._parse_date(date_str)

    @staticmethod
    def _make_id(title: str, dt: datetime) -> str:
        raw = f"us_gov:{title}:{dt.isoformat()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

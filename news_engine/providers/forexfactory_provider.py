from __future__ import annotations

import hashlib
from typing import List, Dict, Any, Optional
import xml.etree.ElementTree as ET

import pandas as pd
import requests

from news_engine.providers.base_provider import BaseNewsProvider


class ForexFactoryProvider(BaseNewsProvider):
    """
    ForexFactory/FairEconomy weekly calendar provider.

    Standard output:
    time, currency, event, impact, actual, forecast, previous, news_id

    ``news_id`` is the canonical ForexFactory calendar id taken from the
    event's <url> (e.g. ``388-jn-bank-lending-yy``); it is stable across
    refreshes so the cache can detect new/updated events. Feed times are
    published in Eastern Time and are converted to UTC so every consumer
    (Telegram alerts, dashboards, trading engine) shares one timezone.
    """

    DEFAULT_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.xml"
    _NY = None

    def __init__(
        self,
        url: str = DEFAULT_URL,
        timeout: int = 30,
        high_medium_only: bool = True,
    ):
        self.url = url
        self.timeout = timeout
        self.high_medium_only = high_medium_only
        if ForexFactoryProvider._NY is None:
            from zoneinfo import ZoneInfo
            ForexFactoryProvider._NY = ZoneInfo("America/New_York")

    def fetch_events(self) -> List[Dict[str, Any]]:
        response = requests.get(self.url, timeout=self.timeout)
        response.raise_for_status()

        root = ET.fromstring(response.content)

        events = []

        for item in root.findall(".//event"):
            event = self._parse_event(item)

            if event is None:
                continue

            if self.high_medium_only and event["impact"] not in ["HIGH", "MEDIUM"]:
                continue

            events.append(event)

        events = sorted(events, key=lambda x: x["time"])
        return events

    def _parse_event(self, item) -> Optional[Dict[str, Any]]:
        title = self._get_text(item, "title")
        country = self._get_text(item, "country")
        date_text = self._get_text(item, "date")
        time_text = self._get_text(item, "time")
        impact = self._get_text(item, "impact")
        forecast = self._get_text(item, "forecast")
        previous = self._get_text(item, "previous")
        actual = self._get_text(item, "actual")
        url = self._get_text(item, "url")

        if not title or not date_text:
            return None

        event_time = self._parse_datetime(date_text, time_text)

        if pd.isna(event_time):
            return None

        news_id = self._make_news_id(url, event_time, country, title)

        return {
            "news_id": news_id,
            "time": event_time,
            "currency": self._clean_currency(country),
            "event": title,
            "impact": self._normalize_impact(impact),
            "actual": self._safe_float(actual),
            "forecast": self._safe_float(forecast),
            "previous": self._safe_float(previous),
        }

    def _get_text(self, item, tag: str) -> str:
        node = item.find(tag)
        if node is None or node.text is None:
            return ""
        return str(node.text).strip()

    def _parse_datetime(self, date_text: str, time_text: str):
        raw = f"{date_text} {time_text}".strip()

        raw = (
            raw.replace("All Day", "00:00")
            .replace("Tentative", "00:00")
            .replace("Day 1", "00:00")
            .replace("Day 2", "00:00")
        )

        parsed = pd.to_datetime(raw, errors="coerce")

        if pd.isna(parsed):
            return parsed

        # Feed publishes ForexFactory calendar times in Eastern Time; convert
        # to UTC so the DB + all consumers share one canonical timezone.
        if parsed.tzinfo is None:
            parsed = parsed.tz_localize(ForexFactoryProvider._NY)
        return parsed.tz_convert("UTC").to_pydatetime()

    def _make_news_id(self, url: str, event_time, country: str, title: str) -> str:
        """Stable id: ForexFactory calendar id from <url>, else deterministic hash."""
        if url:
            # e.g. https://www.forexfactory.com/calendar/388-jn-bank-lending-yy
            last = url.rstrip("/").split("/")[-1]
            if last and not last.lower() in ("calendar",):
                return last

        # Deterministic fallback: currency + event name + UTC time
        time_str = event_time.strftime("%Y%m%d_%H%M%S")
        currency = self._clean_currency(country).upper().strip()
        name = "".join(c if c.isalnum() else "_" for c in str(title).upper().strip())
        name = "_".join(part for part in name.split("_") if part)[:40]
        raw = f"{currency}_{name}_{time_str}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]

    def _clean_currency(self, value: Any) -> str:
        v = str(value or "").upper().strip()

        mapping = {
            "USD": "USD",
            "EUR": "EUR",
            "GBP": "GBP",
            "JPY": "JPY",
            "CAD": "CAD",
            "AUD": "AUD",
            "NZD": "NZD",
            "CHF": "CHF",
            "CNY": "CNY",
        }

        return mapping.get(v, v or "UNKNOWN")

    def _normalize_impact(self, value: Any) -> str:
        v = str(value or "").upper().strip()

        if "HIGH" in v:
            return "HIGH"

        if "MEDIUM" in v:
            return "MEDIUM"

        if "LOW" in v:
            return "LOW"

        return "LOW"

    def _safe_float(self, value: Any):
        try:
            if value is None:
                return None

            v = str(value).strip()

            if v in ["", "-", "—"]:
                return None

            v = (
                v.replace("%", "")
                .replace(",", "")
                .replace("K", "")
                .replace("M", "")
                .replace("B", "")
            )

            return float(v)
        except Exception:
            return None
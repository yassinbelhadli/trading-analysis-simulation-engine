from datetime import datetime
from typing import List, Dict

from news_engine.providers.forexfactory_provider import ForexFactoryProvider
from news_engine.news_cache import NewsCache
from news_engine.fundamental_analyzer import FundamentalAnalyzer
from news_engine.event_aggregator import EventAggregator
from news_engine.fundamental_state import FundamentalState


class LiveNewsUpdater:

    def __init__(self):
        self.provider = ForexFactoryProvider()
        self.cache = NewsCache()
        self.analyzer = FundamentalAnalyzer()
        self.aggregator = EventAggregator()
        self.state = FundamentalState()

    def check_updates(self) -> List[Dict]:
        print(f"[{datetime.now()}] Checking ForexFactory...")
        return self.provider.fetch_events()

    def compare_cache(self, downloaded_events: List[Dict]):
        cached_events = self.cache.load_events()

        cache_index = {}
        for event in cached_events:
            news_id = event.get("news_id")
            if news_id:
                cache_index[str(news_id)] = event

        new_events = []
        updated_events = []

        for event in downloaded_events:
            news_id = event.get("news_id")

            if not news_id:
                # Defense in depth: a provider that forgets the id must never
                # silently drop every event again. Generate a stable id from
                # the event payload (same scheme as the CSV repository).
                import logging
                logging.getLogger(__name__).warning(
                    "event without news_id; generated fallback id: %s | %s",
                    event.get("currency"), event.get("event"),
                )
                news_id = self._make_fallback_news_id(event)
                event["news_id"] = news_id

            if str(news_id) not in cache_index:
                new_events.append(event)
                continue

            cached = cache_index[str(news_id)]

            changed = (
                self._normalize_value(cached.get("actual")) != self._normalize_value(event.get("actual"))
                or self._normalize_value(cached.get("forecast")) != self._normalize_value(event.get("forecast"))
                or self._normalize_value(cached.get("previous")) != self._normalize_value(event.get("previous"))
            )

            if changed:
                updated_events.append(event)

        print(f"New Events     : {len(new_events)}")
        print(f"Updated Events : {len(updated_events)}")

        return new_events, updated_events

    @staticmethod
    def _make_fallback_news_id(event: Dict) -> str:
        """Deterministic id from currency + event name + time (ISO 8601 slug)."""
        import hashlib

        currency = str(event.get("currency", "UNK")).upper().strip()
        name = str(event.get("event", "UNKNOWN")).upper().strip()
        name = "".join(c if c.isalnum() else "_" for c in name)
        name = "_".join(part for part in name.split("_") if part)[:40]

        time_val = event.get("time")
        if time_val is None:
            time_str = "UNKNOWN_TIME"
        else:
            try:
                import pandas as pd
                parsed = pd.to_datetime(time_val, errors="coerce")
                time_str = parsed.strftime("%Y%m%d_%H%M%S") if not pd.isna(parsed) else "UNKNOWN_TIME"
            except Exception:
                time_str = "UNKNOWN_TIME"

        raw = f"{currency}_{name}_{time_str}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]

    def process_new_events(self, events: List[Dict]):
        if not events:
            return

        print(f"\nProcessing {len(events)} new events...")

        for event in events:
            self.cache.add_event(event)
            print(f"[NEW] {event.get('currency')} | {event.get('event')} | {event.get('time')}")

    def process_updated_events(self, events: List[Dict]):
        if not events:
            return

        print(f"\nProcessing {len(events)} updated events...")

        for event in events:
            news_id = event.get("news_id")

            if not news_id:
                continue

            self.cache.update_event(news_id, event)
            print(f"[UPDATED] {event.get('currency')} | {event.get('event')} | {event.get('time')}")

    def run_analysis(self):
        pending_events = self.cache.get_pending_events()

        if not pending_events:
            print("No pending events for analysis.")
            return

        print(f"\nAnalyzing {len(pending_events)} pending events...")

        analyzed_results = []
        analyzed_events = []

        for event in pending_events:
            actual = event.get("actual")

            if self._is_empty_value(actual):
                continue

            result = self.analyzer.analyze_event(
                event=event.get("event"),
                currency=event.get("currency"),
                impact=event.get("impact"),
                actual=self._safe_float(event.get("actual")),
                forecast=self._safe_float(event.get("forecast")),
                previous=self._safe_float(event.get("previous")),
            )

            analyzed_results.append(result)
            analyzed_events.append(event)

            self.cache.mark_analyzed(event["news_id"])
            self.cache.mark_processed(event["news_id"])

            print(
                f"[ANALYZED] {event.get('currency')} | "
                f"{event.get('event')} | "
                f"{result.currency_bias} | "
                f"Strength={result.strength}"
            )

        if not analyzed_results:
            return

        aggregated = self.aggregator.aggregate(analyzed_results)
        decision = aggregated.to_dict()

        last_event = analyzed_events[-1].get("event", "") if analyzed_events else ""
        impact = analyzed_events[-1].get("impact", "") if analyzed_events else ""

        self.state.update_currency(
            currency=decision["currency"],
            bias=decision["bias"],
            strength=decision["strength"],
            confidence=decision["confidence"],
            reason=decision["reason"],
            last_event=last_event,
            impact=impact,
            source="ForexFactory",
        )

        print("\n==============================")
        print("FINAL FUNDAMENTAL DECISION")
        print("==============================")
        print(decision)

    def notify(self):
        pass

    def update_entry_manager(self):
        pass

    def run(self):
        downloaded = self.check_updates()

        new_events, updated_events = self.compare_cache(downloaded)

        self.process_new_events(new_events)
        self.process_updated_events(updated_events)

        self.run_analysis()
        self.notify()
        self.update_entry_manager()

    def _normalize_value(self, value):
        if self._is_empty_value(value):
            return None

        return str(value).strip()

    def _is_empty_value(self, value) -> bool:
        if value is None:
            return True

        value = str(value).strip().lower()
        return value in ["", "nan", "none", "nat"]

    def _safe_float(self, value):
        if self._is_empty_value(value):
            return None

        try:
            return float(str(value).replace("%", "").replace(",", "").strip())
        except Exception:
            return None
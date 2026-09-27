# news_cache.py
from pathlib import Path
from typing import List, Dict, Any, Optional

import pandas as pd

from news_engine.repositories.csv_repository import CSVNewsRepository


class NewsCache:
    def __init__(self, cache_path: str | Path = "data/processed/news_cache.csv"):
        self.repository = CSVNewsRepository(cache_path)

    def load_events(self) -> List[Dict[str, Any]]:
        return self.repository.load_events()

    def save_events(self, events: List[Dict[str, Any]]) -> None:
        self.repository.save_events(events)

    def add_event(self, event: Dict[str, Any]) -> None:
        self.repository.add_event(event)

    def update_event(self, news_id: str, updates: Dict[str, Any]) -> None:
        self.repository.update_event(news_id, updates)

    def get_event(self, news_id: str) -> Optional[Dict[str, Any]]:
        return self.repository.get_event(news_id)

    def event_exists(self, news_id: str) -> bool:
        return self.repository.event_exists(news_id)

    def get_pending_events(self) -> List[Dict[str, Any]]:
        return self.repository.get_pending_events()

    def mark_processed(self, news_id: str) -> None:
        self.repository.mark_processed(news_id)

    def mark_analyzed(self, news_id: str) -> None:
        self.repository.mark_analyzed(news_id)

    def mark_telegram_sent(self, news_id: str) -> None:
        self.repository.mark_telegram_sent(news_id)

    def mark_entry_processed(self, news_id: str) -> None:
        self.repository.mark_entry_processed(news_id)

    def to_dataframe(self) -> pd.DataFrame:
        events = self.load_events()
        return pd.DataFrame(events)

    def clear(self) -> None:
        self.repository.save_events([])
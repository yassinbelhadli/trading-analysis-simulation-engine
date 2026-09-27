from abc import ABC, abstractmethod
from typing import List, Dict, Optional


class BaseNewsRepository(ABC):
    """
    Base contract for all News repositories.

    Any storage backend (CSV, PostgreSQL, MySQL...)
    must implement this interface.
    """

    @abstractmethod
    def load_events(self) -> List[Dict]:
        """Load all news events."""
        pass

    @abstractmethod
    def save_events(self, events: List[Dict]) -> None:
        """Replace all stored events."""
        pass

    @abstractmethod
    def add_event(self, event: Dict) -> None:
        """Insert one event."""
        pass

    @abstractmethod
    def update_event(self, news_id: str, updates: Dict) -> None:
        """Update an existing event."""
        pass

    @abstractmethod
    def get_event(self, news_id: str) -> Optional[Dict]:
        """Return one event by ID."""
        pass

    @abstractmethod
    def event_exists(self, news_id: str) -> bool:
        """Check if event already exists."""
        pass

    @abstractmethod
    def get_pending_events(self) -> List[Dict]:
        """
        Events not analyzed yet.
        """
        pass

    @abstractmethod
    def mark_processed(self, news_id: str) -> None:
        pass

    @abstractmethod
    def mark_analyzed(self, news_id: str) -> None:
        pass

    @abstractmethod
    def mark_telegram_sent(self, news_id: str) -> None:
        pass

    @abstractmethod
    def mark_entry_processed(self, news_id: str) -> None:
        pass
"""Abstract base for calendar data sources."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from economic_calendar.models import EconomicEvent


class CalendarSource(ABC):
    """Base class for all calendar data source adapters."""

    source_name: str = "unknown"

    @abstractmethod
    async def fetch(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[EconomicEvent]:
        """Fetch US economic events from this source.

        Args:
            start_date: ISO date string (YYYY-MM-DD). None = today.
            end_date: ISO date string (YYYY-MM-DD). None = today + 7 days.

        Returns:
            List of normalized EconomicEvent objects.
        """
        ...

    @abstractmethod
    async def fetch_event_detail(self, external_id: str) -> Optional[EconomicEvent]:
        """Fetch detail for a single event by provider ID."""
        ...

    async def health_check(self) -> bool:
        """Return True if the source is reachable."""
        try:
            await self.fetch(start_date="2025-01-01", end_date="2025-01-02")
            return True
        except Exception:
            return False

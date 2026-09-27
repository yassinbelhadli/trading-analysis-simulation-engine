"""Scheduler interfaces for the Economic Calendar.

Defines the contract that Phase 3 will implement:

  - T-60 protection window (block new entries)
  - T-30 notification (pre-release alert)
  - T-5 notification (imminent release alert)
  - Weekly summary
  - Actual release handling

Phase 2 ONLY defines these interfaces and their data contracts.
No trading logic or Telegram sending is implemented here.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


# ── Event payloads (data contracts for Phase 3 consumers) ────────


@dataclass
class CalendarAlert:
    """Generic calendar alert payload — emitted by scheduler, consumed by Phase 3."""

    alert_type: str             # t60_block | t30_alert | t5_alert | weekly_summary | released
    event_title: str
    event_id: str               # CalendarEvent.id
    scheduled_at_utc: datetime
    impact: str
    category: str
    relevant_symbols: List[str]
    minutes_until: float
    forecast: Optional[float] = None
    previous: Optional[float] = None
    actual: Optional[float] = None
    surprise: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_type": self.alert_type,
            "event_title": self.event_title,
            "event_id": self.event_id,
            "scheduled_at_utc": self.scheduled_at_utc.isoformat(),
            "impact": self.impact,
            "category": self.category,
            "relevant_symbols": self.relevant_symbols,
            "minutes_until": self.minutes_until,
            "forecast": self.forecast,
            "previous": self.previous,
            "actual": self.actual,
            "surprise": self.surprise,
            "metadata": self.metadata,
        }


@dataclass
class WeeklySummary:
    """Weekly calendar summary payload."""

    week_start: datetime
    week_end: datetime
    total_events: int
    high_impact_count: int
    medium_impact_count: int
    low_impact_count: int
    events: List[Dict[str, Any]]
    top_events: List[Dict[str, Any]]  # highest impact events

    def to_dict(self) -> Dict[str, Any]:
        return {
            "week_start": self.week_start.isoformat(),
            "week_end": self.week_end.isoformat(),
            "total_events": self.total_events,
            "high_impact_count": self.high_impact_count,
            "medium_impact_count": self.medium_impact_count,
            "low_impact_count": self.low_impact_count,
            "events": self.events,
            "top_events": self.top_events,
        }


# ── Abstract scheduler interface ──────────────────────────────────


class CalendarSchedulerInterface(ABC):
    """Interface for calendar-based scheduled operations.

    Phase 3 will provide a concrete implementation.
    Phase 2 defines the contract.
    """

    @abstractmethod
    async def check_t60_window(self, now: Optional[datetime] = None) -> List[CalendarAlert]:
        """Check for events entering the T-60 protection window.

        Returns alerts for HIGH/MEDIUM events within the next 60 minutes
        that have not already been alerted.

        Phase 3 will use this to:
          - Block new trade entries
          - Emit TRADE_BLOCKED events if applicable
        """
        ...

    @abstractmethod
    async def check_t30_alerts(self, now: Optional[datetime] = None) -> List[CalendarAlert]:
        """Check for T-30 pre-release notification window.

        Returns alerts for HIGH/MEDIUM events within 30-31 minutes
        (to avoid duplicate alerts).

        Phase 3 will use this to send Telegram notifications.
        """
        ...

    @abstractmethod
    async def check_t5_alerts(self, now: Optional[datetime] = None) -> List[CalendarAlert]:
        """Check for T-5 imminent-release notification window.

        Returns alerts for HIGH events within 5-6 minutes.

        Phase 3 will use this to send Telegram notifications.
        """
        ...

    @abstractmethod
    async def check_actual_release(self, now: Optional[datetime] = None) -> List[CalendarAlert]:
        """Check for events that just released their actual value.

        Returns alerts for events whose status changed to RELEASED
        since last check.

        Phase 3 will use this to send post-release Telegram messages.
        """
        ...

    @abstractmethod
    async def generate_weekly_summary(
        self,
        week_start: Optional[datetime] = None,
    ) -> Optional[WeeklySummary]:
        """Generate a weekly calendar summary.

        Args:
            week_start: Monday of the target week (defaults to current week).

        Phase 3 will use this to send weekly Telegram summaries.
        """
        ...


# ── Null implementation (Phase 2 default) ──────────────────────────


class NullCalendarScheduler(CalendarSchedulerInterface):
    """No-op implementation.  Phase 3 replaces this."""

    async def check_t60_window(self, now: Optional[datetime] = None) -> List[CalendarAlert]:
        return []

    async def check_t30_alerts(self, now: Optional[datetime] = None) -> List[CalendarAlert]:
        return []

    async def check_t5_alerts(self, now: Optional[datetime] = None) -> List[CalendarAlert]:
        return []

    async def check_actual_release(self, now: Optional[datetime] = None) -> List[CalendarAlert]:
        return []

    async def generate_weekly_summary(
        self,
        week_start: Optional[datetime] = None,
    ) -> Optional[WeeklySummary]:
        return None


# ── Module-level default ──────────────────────────────────────────
calendar_scheduler: CalendarSchedulerInterface = NullCalendarScheduler()

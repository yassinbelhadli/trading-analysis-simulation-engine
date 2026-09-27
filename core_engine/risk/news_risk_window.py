"""News Risk Window — T-60 protection state for the trading engine.

Manages which symbols are in a news-risk-active state and provides
the structured reaction context for the ICT/SMC engine.

States per symbol:
  NORMAL -> NEWS_RISK_ACTIVE (T-60) -> NEWS_RELEASED (actual published)
           -> REACTION_WINDOW (15 min after release) -> NORMAL

Rules:
  - NEWS_RISK_ACTIVE blocks NEW ENTRY only
  - Existing positions are NOT automatically closed
  - MEDIUM impact events follow configurable policy (default: block)
  - LOW impact events never trigger protection
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class NewsRiskState(str, Enum):
    """Per-symbol news risk state."""
    NORMAL = "NORMAL"
    NEWS_RISK_ACTIVE = "NEWS_RISK_ACTIVE"
    NEWS_RELEASED = "NEWS_RELEASED"
    REACTION_WINDOW = "REACTION_WINDOW"


@dataclass
class ActiveNewsEvent:
    """Tracks an active news event within the risk window."""
    event_id: str
    event_title: str
    scheduled_at_utc: datetime
    impact: str
    category: str
    relevant_symbols: List[str]
    forecast: Optional[float] = None
    previous: Optional[float] = None
    actual: Optional[float] = None
    surprise: Optional[float] = None
    released_at: Optional[datetime] = None
    t60_alerted: bool = False
    t30_alerted: bool = False
    t5_alerted: bool = False
    released_emitted: bool = False

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_title": self.event_title,
            "scheduled_at_utc": self.scheduled_at_utc.isoformat(),
            "impact": self.impact,
            "category": self.category,
            "relevant_symbols": self.relevant_symbols,
            "forecast": self.forecast,
            "previous": self.previous,
            "actual": self.actual,
            "surprise": self.surprise,
            "released_at": self.released_at.isoformat() if self.released_at else None,
        }


@dataclass
class ReactionContext:
    """Structured reaction context exposed to the trading engine after release.

    The ICT/SMC engine uses this to decide if there is a valid setup.
    This does NOT generate trades — it only provides context.
    """
    event_title: str
    event_id: str
    actual: Optional[float]
    forecast: Optional[float]
    previous: Optional[float]
    surprise: Optional[float]
    impact: str
    category: str
    affected_symbols: List[str]
    release_timestamp: datetime
    reaction_window_active: bool
    minutes_since_release: float

    def to_dict(self) -> dict:
        return {
            "event_title": self.event_title,
            "event_id": self.event_id,
            "actual": self.actual,
            "forecast": self.forecast,
            "previous": self.previous,
            "surprise": self.surprise,
            "impact": self.impact,
            "category": self.category,
            "affected_symbols": self.affected_symbols,
            "release_timestamp": self.release_timestamp.isoformat(),
            "reaction_window_active": self.reaction_window_active,
            "minutes_since_release": self.minutes_since_release,
        }


class NewsRiskWindow:
    """Manages news-risk state per symbol.

    Thread-safe via asyncio (single event loop). All state is in-memory;
    the CalendarEvent DB table is the durable source of truth.
    """

    def __init__(
        self,
        t60_minutes: float = 60.0,
        reaction_window_minutes: float = 15.0,
        block_medium: bool = True,
    ):
        self.t60_minutes = t60_minutes
        self.reaction_window_minutes = reaction_window_minutes
        self.block_medium = block_medium

        # Per-symbol state
        self._states: Dict[str, NewsRiskState] = {}
        # Active events by event_id
        self._active_events: Dict[str, ActiveNewsEvent] = {}
        # Reaction contexts by symbol (populated after release)
        self._reaction_contexts: Dict[str, ReactionContext] = {}

    # ── State queries ─────────────────────────────────────────────

    def get_state(self, symbol: str) -> NewsRiskState:
        """Get current news risk state for a symbol."""
        return self._states.get(symbol, NewsRiskState.NORMAL)

    def is_entry_blocked(self, symbol: str) -> bool:
        """Return True if new entry is blocked for this symbol.

        Only NEWS_RISK_ACTIVE blocks entries.
        REACTION_WINDOW does NOT block — the engine may want to trade
        the reaction if ICT/SMC confirms a setup.
        """
        state = self.get_state(symbol)
        return state == NewsRiskState.NEWS_RISK_ACTIVE

    def get_block_reason(self, symbol: str) -> Optional[str]:
        """Return a human-readable block reason if entry is blocked."""
        if not self.is_entry_blocked(symbol):
            return None

        # Find the blocking event
        for event in self._active_events.values():
            if symbol in event.relevant_symbols:
                minutes = self._minutes_until(event.scheduled_at_utc)
                return (
                    f"NEWS_RISK_WINDOW: {event.impact}-impact USD news "
                    f"'{event.event_title}' scheduled within {int(minutes)} minutes"
                )
        return "NEWS_RISK_WINDOW: Active news risk"

    def get_active_events(self, symbol: Optional[str] = None) -> List[ActiveNewsEvent]:
        """Get active news events, optionally filtered by symbol."""
        events = list(self._active_events.values())
        if symbol:
            events = [e for e in events if symbol in e.relevant_symbols]
        return events

    def get_reaction_context(self, symbol: str) -> Optional[ReactionContext]:
        """Get the reaction context for a recently released event.

        The ICT/SMC engine checks this to see if there is news context
        for a potential trade. Does NOT generate trades.
        """
        return self._reaction_contexts.get(symbol)

    # ── State transitions ─────────────────────────────────────────

    def activate_t60(
        self,
        event_id: str,
        event_title: str,
        scheduled_at_utc: datetime,
        impact: str,
        category: str,
        relevant_symbols: List[str],
        forecast: Optional[float] = None,
        previous: Optional[float] = None,
    ) -> None:
        """Activate T-60 protection for the given event's symbols.

        Called by the scheduler when an event enters the T-60 window.
        """
        if event_id in self._active_events:
            return  # already tracked

        event = ActiveNewsEvent(
            event_id=event_id,
            event_title=event_title,
            scheduled_at_utc=scheduled_at_utc,
            impact=impact,
            category=category,
            relevant_symbols=relevant_symbols,
            forecast=forecast,
            previous=previous,
        )
        self._active_events[event_id] = event

        for symbol in relevant_symbols:
            self._states[symbol] = NewsRiskState.NEWS_RISK_ACTIVE
            logger.info(
                "NEWS_RISK: %s -> NEWS_RISK_ACTIVE (event=%s, impact=%s)",
                symbol, event_title, impact,
            )

    def activate_release(
        self,
        event_id: str,
        actual: Optional[float] = None,
        surprise: Optional[float] = None,
    ) -> None:
        """Transition to NEWS_RELEASED when actual value is published.

        Called by the scheduler when an event's actual becomes available.
        """
        event = self._active_events.get(event_id)
        if event is None:
            return

        event.actual = actual
        event.surprise = surprise
        event.released_at = datetime.now(timezone.utc)

        for symbol in event.relevant_symbols:
            self._states[symbol] = NewsRiskState.NEWS_RELEASED
            logger.info(
                "NEWS_RISK: %s -> NEWS_RELEASED (event=%s, actual=%s)",
                symbol, event.event_title, actual,
            )

    def activate_reaction_window(self, event_id: str) -> None:
        """Transition to REACTION_WINDOW after the release cools down.

        Called by the scheduler ~15 min after release.
        """
        event = self._active_events.get(event_id)
        if event is None:
            return

        for symbol in event.relevant_symbols:
            self._states[symbol] = NewsRiskState.REACTION_WINDOW
            # Build reaction context for the engine
            self._reaction_contexts[symbol] = ReactionContext(
                event_title=event.event_title,
                event_id=event.event_id,
                actual=event.actual,
                forecast=event.forecast,
                previous=event.previous,
                surprise=event.surprise,
                impact=event.impact,
                category=event.category,
                affected_symbols=event.relevant_symbols,
                release_timestamp=event.released_at or datetime.now(timezone.utc),
                reaction_window_active=True,
                minutes_since_release=self._minutes_since(event.released_at) if event.released_at else 0,
            )
            logger.info(
                "NEWS_RISK: %s -> REACTION_WINDOW (event=%s)",
                symbol, event.event_title,
            )

    def deactivate(self, event_id: str) -> None:
        """Return symbols to NORMAL after the reaction window expires.

        Called by the scheduler after reaction_window_minutes.
        """
        event = self._active_events.pop(event_id, None)
        if event is None:
            return

        for symbol in event.relevant_symbols:
            # Only deactivate if no other active event covers this symbol
            still_active = any(
                symbol in e.relevant_symbols
                for e in self._active_events.values()
            )
            if not still_active:
                self._states[symbol] = NewsRiskState.NORMAL
                self._reaction_contexts.pop(symbol, None)
                logger.info("NEWS_RISK: %s -> NORMAL (event cleared)", symbol)

    def cleanup_stale(self, now: Optional[datetime] = None) -> int:
        """Remove events that are well past their release + reaction window.

        Safety net to prevent stuck states. Returns number of cleaned events.
        """
        now = now or datetime.now(timezone.utc)
        stale_ids = []

        for eid, event in self._active_events.items():
            # If event is more than t60 + reaction_window + 30 min past scheduled, it's stale
            cutoff = event.scheduled_at_utc + timedelta(
                minutes=self.t60_minutes + self.reaction_window_minutes + 30
            )
            if now > cutoff:
                stale_ids.append(eid)

        for eid in stale_ids:
            self.deactivate(eid)

        if stale_ids:
            logger.warning("NEWS_RISK: cleaned up %d stale events", len(stale_ids))

        return len(stale_ids)

    def reset(self) -> None:
        """Reset all state. For testing or emergency clear."""
        self._states.clear()
        self._active_events.clear()
        self._reaction_contexts.clear()

    # ── Helpers ───────────────────────────────────────────────────

    @staticmethod
    def _minutes_until(dt: datetime) -> float:
        now = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0, (dt - now).total_seconds() / 60.0)

    @staticmethod
    def _minutes_since(dt: Optional[datetime]) -> float:
        if dt is None:
            return 0.0
        now = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0, (now - dt).total_seconds() / 60.0)

    def to_dict(self) -> dict:
        """Serialize full state for debugging/API."""
        return {
            "states": {s: st.value for s, st in self._states.items()},
            "active_events": {eid: e.to_dict() for eid, e in self._active_events.items()},
            "reaction_contexts": {s: rc.to_dict() for s, rc in self._reaction_contexts.items()},
        }


# ── Module-level singleton ──────────────────────────────────────
news_risk_window = NewsRiskWindow()

"""Normalized internal EconomicEvent model.

The rest of the application depends ONLY on this dataclass — never on
BLS / BEA / investing.com response formats directly.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class EconomicEvent:
    """Provider-agnostic normalized economic event."""

    source: str                   # bls | bea | federal_reserve | investing_com | forexfactory | manual
    external_id: str              # provider-specific unique key
    title: str
    scheduled_at: datetime        # always UTC

    country: str = "US"
    currency: str = "USD"
    category: str = "other"       # inflation | employment | gdp | monetary | housing | consumer | manufacturing | trade | other
    impact: str = "LOW"           # HIGH | MEDIUM | LOW

    forecast: Optional[float] = None
    previous: Optional[float] = None
    actual: Optional[float] = None
    surprise: Optional[float] = None

    status: str = "SCHEDULED"     # SCHEDULED | RELEASED | REVISED | CANCELLED
    description: Optional[str] = None
    source_url: Optional[str] = None
    relevant_symbols: List[str] = field(default_factory=list)
    actual_released_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["scheduled_at"] = self.scheduled_at.isoformat()
        if self.actual_released_at:
            d["actual_released_at"] = self.actual_released_at.isoformat()
        return d

    @property
    def minutes_until(self) -> float:
        """Minutes from now until scheduled time (negative = past)."""
        now = datetime.now(timezone.utc)
        if self.scheduled_at.tzinfo is None:
            scheduled = self.scheduled_at.replace(tzinfo=timezone.utc)
        else:
            scheduled = self.scheduled_at
        delta = scheduled - now
        return delta.total_seconds() / 60.0

    @property
    def is_upcoming(self) -> bool:
        now = datetime.now(timezone.utc)
        if self.scheduled_at.tzinfo is None:
            scheduled = self.scheduled_at.replace(tzinfo=timezone.utc)
        else:
            scheduled = self.scheduled_at
        return self.status == "SCHEDULED" and scheduled > now

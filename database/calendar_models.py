"""CalendarEvent — single source of truth for US economic calendar data.

Shared by:
  - Telegram notification pipeline (via EventNotificationBridge)
  - Trading Risk Engine (via ExecutionGuard news protection)

Canonical timestamp is UTC.  `scheduled_at_et` is a convenience column
derived from UTC at write-time and must never be the authoritative source.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text as sa_text,
)
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class CalendarEvent(Base):
    """Persisted US economic calendar event — single source of truth."""

    __tablename__ = "calendar_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)

    # ── source tracking ──────────────────────────────────────────
    source: Mapped[str] = mapped_column(
        String(30), nullable=False, index=True,
        comment="bls | bea | federal_reserve | investing_com | forexfactory | manual",
    )
    external_id: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="Provider-specific unique identifier",
    )

    # ── classification ───────────────────────────────────────────
    country: Mapped[str] = mapped_column(String(5), nullable=False, default="US")
    currency: Mapped[str] = mapped_column(String(5), nullable=False, default="USD")
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(
        String(50), nullable=False, default="other",
        comment="inflation | employment | gdp | monetary | housing | consumer | manufacturing | trade | other",
    )
    impact: Mapped[str] = mapped_column(
        String(10), nullable=False, default="LOW",
        comment="HIGH | MEDIUM | LOW",
    )

    # ── timing ───────────────────────────────────────────────────
    scheduled_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True,
    )
    scheduled_at_et: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Eastern Time — derived from UTC, convenience only",
    )

    # ── data values ──────────────────────────────────────────────
    forecast: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    previous: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    actual: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    surprise: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="actual - forecast (null until actual is released)",
    )

    # ── lifecycle ────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="SCHEDULED", index=True,
        comment="SCHEDULED | RELEASED | REVISED | CANCELLED",
    )

    # ── market relevance ─────────────────────────────────────────
    relevant_symbols: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True,
        comment='["XAUUSD", "BTCUSD", "NASDAQ"]',
    )

    # ── source metadata ──────────────────────────────────────────
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow,
    )
    actual_released_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="UTC timestamp when actual value first appeared",
    )

    # ── staleness metadata ───────────────────────────────────────
    data_quality: Mapped[str] = mapped_column(
        String(20), nullable=False, default="FRESH",
        comment="FRESH | STALE | UNAVAILABLE",
    )
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_calendar_event_source_external_id"),
        Index("ix_calendar_events_scheduled_impact", "scheduled_at_utc", "impact"),
        Index("ix_calendar_events_category_status", "category", "status"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source": self.source,
            "external_id": self.external_id,
            "country": self.country,
            "currency": self.currency,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "impact": self.impact,
            "scheduled_at_utc": self.scheduled_at_utc.isoformat() if self.scheduled_at_utc else None,
            "scheduled_at_et": self.scheduled_at_et.isoformat() if self.scheduled_at_et else None,
            "forecast": self.forecast,
            "previous": self.previous,
            "actual": self.actual,
            "surprise": self.surprise,
            "status": self.status,
            "relevant_symbols": self.relevant_symbols,
            "source_url": self.source_url,
            "fetched_at": self.fetched_at.isoformat() if self.fetched_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "actual_released_at": self.actual_released_at.isoformat() if self.actual_released_at else None,
            "data_quality": self.data_quality,
            "consecutive_failures": self.consecutive_failures,
        }

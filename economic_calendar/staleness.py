"""Stale-data policy for the Economic Calendar.

Defines three data-quality states:
  - FRESH:      Last fetch succeeded; data is current.
  - STALE:      Last fetch failed, but last known data is still usable
                within a defined grace period.
  - UNAVAILABLE: No valid data available (never fetched, or grace expired).

The Trading Risk Engine uses these states to decide whether to block
new entries during the T-60 window.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional


class DataQuality(str, Enum):
    FRESH = "FRESH"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"


# Default staleness thresholds
STALE_THRESHOLD_HOURS = 6     # after 6h of consecutive failures → STALE
UNAVAILABLE_THRESHOLD_HOURS = 24  # after 24h of consecutive failures → UNAVAILABLE


class StalenessPolicy:
    """Evaluates data quality based on fetch history.

    Usage::

        policy = StalenessPolicy()
        quality = policy.evaluate(
            last_success_at=datetime.utcnow() - timedelta(hours=2),
            consecutive_failures=1,
        )
        assert quality == DataQuality.FRESH
    """

    def __init__(
        self,
        stale_threshold_hours: float = STALE_THRESHOLD_HOURS,
        unavailable_threshold_hours: float = UNAVAILABLE_THRESHOLD_HOURS,
    ):
        self.stale_threshold = timedelta(hours=stale_threshold_hours)
        self.unavailable_threshold = timedelta(hours=unavailable_threshold_hours)

    def evaluate(
        self,
        last_success_at: Optional[datetime],
        consecutive_failures: int = 0,
        now: Optional[datetime] = None,
    ) -> DataQuality:
        """Evaluate current data quality.

        Args:
            last_success_at: UTC timestamp of last successful fetch.
            consecutive_failures: Number of consecutive fetch failures.
            now: Current UTC time (defaults to datetime.utcnow()).

        Returns:
            DataQuality enum value.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        # Never fetched successfully
        if last_success_at is None:
            return DataQuality.UNAVAILABLE

        # Ensure timezone-aware
        if last_success_at.tzinfo is None:
            last_success_at = last_success_at.replace(tzinfo=timezone.utc)

        elapsed = now - last_success_at

        # No failures or very recent success
        if consecutive_failures == 0 or elapsed < self.stale_threshold:
            return DataQuality.FRESH

        if elapsed >= self.unavailable_threshold:
            return DataQuality.UNAVAILABLE

        return DataQuality.STALE

    def should_block_trading(self, quality: DataQuality) -> bool:
        """Should the T-60 protection window block new entries?

        FRESH:    Yes — we have reliable data, apply protection.
        STALE:    Yes — be conservative with stale data.
        UNAVAILABLE: No — we have no data, cannot protect. Let risk
                      engine handle via other guards.
        """
        return quality in (DataQuality.FRESH, DataQuality.STALE)

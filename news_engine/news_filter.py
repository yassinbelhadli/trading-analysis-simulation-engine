from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional
import pandas as pd


@dataclass
class NewsFilterResult:
    allowed: bool
    reason: str
    blocking_event: Optional[str]
    blocking_currency: Optional[str]
    impact: Optional[str]
    minutes_to_event: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class NewsFilter:
    def __init__(
        self,
        block_before_minutes: int = 60,
        block_after_minutes: int = 30,
        block_high_only: bool = True,
    ):
        self.block_before_minutes = block_before_minutes
        self.block_after_minutes = block_after_minutes
        self.block_high_only = block_high_only

    def evaluate(
        self,
        symbol: str,
        current_time,
        calendar,
    ) -> NewsFilterResult:

        current_time = pd.to_datetime(current_time)

        symbol = str(symbol).upper()

        affected_currencies = self._affected_currencies(symbol)

        for event in calendar.get_events():

            event_time = pd.to_datetime(event.time)

            minutes_diff = (
                event_time - current_time
            ).total_seconds() / 60.0

            if event.currency not in affected_currencies:
                continue

            if self.block_high_only and event.impact != "HIGH":
                continue

            before_window = (
                0 <= minutes_diff <= self.block_before_minutes
            )

            after_window = (
                -self.block_after_minutes <= minutes_diff < 0
            )

            if before_window or after_window:
                return NewsFilterResult(
                    allowed=False,
                    reason="HIGH_IMPACT_NEWS_BLOCK",
                    blocking_event=event.event_name,
                    blocking_currency=event.currency,
                    impact=event.impact,
                    minutes_to_event=round(minutes_diff, 2),
                )

        return NewsFilterResult(
            allowed=True,
            reason="NO_NEWS_CONFLICT",
            blocking_event=None,
            blocking_currency=None,
            impact=None,
            minutes_to_event=None,
        )

    def _affected_currencies(self, symbol: str):

        symbol = symbol.upper()

        if "XAU" in symbol:
            return ["USD"]

        if "NAS" in symbol:
            return ["USD"]

        if "USTEC" in symbol:
            return ["USD"]

        if "US30" in symbol:
            return ["USD"]

        if "SPX" in symbol:
            return ["USD"]

        if "BTC" in symbol:
            return ["USD"]

        return ["USD"]
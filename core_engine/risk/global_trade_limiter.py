# global_trade_limiter.py
from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional
import pandas as pd


@dataclass
class GlobalTradeLimitResult:
    allowed: bool
    reason: str
    date: str
    symbol: str
    global_daily_count: int
    max_global_trades_per_day: int
    symbol_daily_count: int
    max_symbol_trades_per_day: int
    priority_score: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class GlobalDailyTradeLimiter:
    def __init__(
        self,
        max_global_trades_per_day: int = 5,
        max_symbol_trades_per_day: int = 3,
        min_priority_score: float = 75.0,
        prefer_a_plus: bool = True,
    ):
        self.max_global_trades_per_day = max_global_trades_per_day
        self.max_symbol_trades_per_day = max_symbol_trades_per_day
        self.min_priority_score = min_priority_score
        self.prefer_a_plus = prefer_a_plus

        self.global_daily_count: Dict[str, int] = {}
        self.symbol_daily_count: Dict[str, Dict[str, int]] = {}

    def reset(self):
        self.global_daily_count = {}
        self.symbol_daily_count = {}

    def build_priority_score(self, row: pd.Series) -> float:
        setup_score = self._safe_float(row.get("Setup_Score", row.get("setup_score", 0)))
        confidence = self._safe_float(row.get("Confidence_Score", row.get("confidence_score", 0)))
        priority = setup_score + confidence * 0.25

        rank = str(row.get("Setup_Rank", row.get("setup_rank", "")))

        if rank == "ELITE_A_PLUS":
            priority += 8
        elif rank == "A_PLUS":
            priority += 5
        elif rank == "A":
            priority += 2

        if bool(row.get("Valid_Sweep", False)):
            priority += 3

        if bool(row.get("MSS", False)):
            priority += 2

        if bool(row.get("CHoCH", False)):
            priority += 1

        return round(priority, 5)

    def evaluate(
        self,
        timestamp,
        symbol: str,
        row: pd.Series,
    ) -> GlobalTradeLimitResult:

        date = str(pd.to_datetime(timestamp).date())
        symbol = str(symbol).upper()
        priority_score = self.build_priority_score(row)

        if date not in self.global_daily_count:
            self.global_daily_count[date] = 0

        if date not in self.symbol_daily_count:
            self.symbol_daily_count[date] = {}

        if symbol not in self.symbol_daily_count[date]:
            self.symbol_daily_count[date][symbol] = 0

        global_count = self.global_daily_count[date]
        symbol_count = self.symbol_daily_count[date][symbol]

        if priority_score < self.min_priority_score:
            return GlobalTradeLimitResult(
                allowed=False,
                reason="GLOBAL_PRIORITY_TOO_LOW",
                date=date,
                symbol=symbol,
                global_daily_count=global_count,
                max_global_trades_per_day=self.max_global_trades_per_day,
                symbol_daily_count=symbol_count,
                max_symbol_trades_per_day=self.max_symbol_trades_per_day,
                priority_score=priority_score,
            )

        if global_count >= self.max_global_trades_per_day:
            return GlobalTradeLimitResult(
                allowed=False,
                reason="GLOBAL_DAILY_LIMIT_REACHED",
                date=date,
                symbol=symbol,
                global_daily_count=global_count,
                max_global_trades_per_day=self.max_global_trades_per_day,
                symbol_daily_count=symbol_count,
                max_symbol_trades_per_day=self.max_symbol_trades_per_day,
                priority_score=priority_score,
            )

        if symbol_count >= self.max_symbol_trades_per_day:
            return GlobalTradeLimitResult(
                allowed=False,
                reason="SYMBOL_DAILY_LIMIT_REACHED",
                date=date,
                symbol=symbol,
                global_daily_count=global_count,
                max_global_trades_per_day=self.max_global_trades_per_day,
                symbol_daily_count=symbol_count,
                max_symbol_trades_per_day=self.max_symbol_trades_per_day,
                priority_score=priority_score,
            )

        return GlobalTradeLimitResult(
            allowed=True,
            reason="ALLOWED",
            date=date,
            symbol=symbol,
            global_daily_count=global_count,
            max_global_trades_per_day=self.max_global_trades_per_day,
            symbol_daily_count=symbol_count,
            max_symbol_trades_per_day=self.max_symbol_trades_per_day,
            priority_score=priority_score,
        )

    def register_trade(self, timestamp, symbol: str):
        date = str(pd.to_datetime(timestamp).date())
        symbol = str(symbol).upper()

        if date not in self.global_daily_count:
            self.global_daily_count[date] = 0

        if date not in self.symbol_daily_count:
            self.symbol_daily_count[date] = {}

        if symbol not in self.symbol_daily_count[date]:
            self.symbol_daily_count[date][symbol] = 0

        self.global_daily_count[date] += 1
        self.symbol_daily_count[date][symbol] += 1

    def _safe_float(self, value, default=0.0) -> float:
        try:
            if pd.isna(value):
                return default
            return float(value)
        except Exception:
            return default
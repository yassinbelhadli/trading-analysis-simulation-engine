from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import pandas as pd


@dataclass
class CachedCandles:
    symbol: str
    timeframe: str
    count: int
    df: pd.DataFrame
    cached_at: datetime
    expires_at: datetime

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        if now is None:
            now = datetime.now(timezone.utc)
        return now >= self.expires_at


CACHE_DURATIONS: Dict[str, timedelta] = {
    "M1": timedelta(seconds=30),
    "M5": timedelta(seconds=90),
    "M15": timedelta(minutes=3),
    "M30": timedelta(minutes=5),
    "H1": timedelta(minutes=10),
    "H4": timedelta(minutes=30),
    "D1": timedelta(hours=2),
    "W1": timedelta(hours=6),
    "MN1": timedelta(hours=12),
}


class CandleBuffer:
    def __init__(self):
        self._cache: Dict[Tuple[str, str, int], CachedCandles] = {}

    def get(self, symbol: str, timeframe: str, count: int) -> Optional[pd.DataFrame]:
        key = (symbol.upper(), timeframe.upper(), count)
        cached = self._cache.get(key)
        if cached is None:
            return None
        if cached.is_expired():
            del self._cache[key]
            return None
        return cached.df.copy()

    def set(self, symbol: str, timeframe: str, count: int, df: pd.DataFrame,
            custom_ttl: Optional[timedelta] = None) -> None:
        key = (symbol.upper(), timeframe.upper(), count)
        now = datetime.now(timezone.utc)
        duration = custom_ttl or CACHE_DURATIONS.get(timeframe.upper(), timedelta(seconds=30))
        self._cache[key] = CachedCandles(
            symbol=symbol.upper(),
            timeframe=timeframe.upper(),
            count=count,
            df=df.copy(),
            cached_at=now,
            expires_at=now + duration,
        )

    def invalidate(self, symbol: str, timeframe: Optional[str] = None,
                   count: Optional[int] = None) -> None:
        keys_to_delete = []
        for (sym, tf, cnt) in self._cache:
            if sym == symbol.upper():
                if timeframe and tf != timeframe.upper():
                    continue
                if count is not None and cnt != count:
                    continue
                keys_to_delete.append((sym, tf, cnt))
        for k in keys_to_delete:
            del self._cache[k]

    def clear(self) -> None:
        self._cache.clear()

    def size(self) -> int:
        return len(self._cache)


candle_buffer = CandleBuffer()

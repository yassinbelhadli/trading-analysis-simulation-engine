from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

import pandas as pd

from core_engine.mt_runtime import MTRuntime
from core_engine.data_feed.candle_buffer import CandleBuffer, candle_buffer
from core_engine.data_feed.symbol_manager import SymbolManager, symbol_cache
from core_engine.data_feed.session_manager import SessionManager, session_manager, SessionAnalysis

REQUIRED_COLUMNS = ["open", "high", "low", "close", "tick_volume", "spread"]
TIMEFRAMES = {
    "M1": 1, "M5": 5, "M15": 15, "M30": 30,
    "H1": 60, "H4": 240, "D1": 1440, "W1": 10080,
}


class MarketData:
    def __init__(self, runtime: Optional[MTRuntime] = None,
                 buffer: Optional[CandleBuffer] = None):
        self._runtime = runtime
        self._buffer = buffer or candle_buffer
        self._symbol_mgr: Optional[SymbolManager] = None

    async def set_runtime(self, runtime: MTRuntime) -> None:
        self._runtime = runtime
        self._symbol_mgr = SymbolManager(runtime)
        await self._symbol_mgr.refresh()

    @property
    def symbol_manager(self) -> Optional[SymbolManager]:
        return self._symbol_mgr

    @property
    def session_manager(self) -> SessionManager:
        return session_manager

    def _validate_df(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        for col in REQUIRED_COLUMNS:
            if col not in df.columns:
                df[col] = 0.0
        return df

    async def get_rates(self, symbol: str, timeframe: str = "M5",
                        count: int = 500) -> pd.DataFrame:
        cached = self._buffer.get(symbol, timeframe, count)
        if cached is not None and not cached.empty:
            return cached

        if self._runtime is None:
            return pd.DataFrame()

        tf_minutes = TIMEFRAMES.get(timeframe.upper(), 5)
        raw = await self._runtime.get_rates(symbol, tf_minutes, count + 1)

        if not raw:
            return pd.DataFrame()

        df = pd.DataFrame(raw)

        if "time" not in df.columns:
            return pd.DataFrame()

        df["time"] = pd.to_datetime(df["time"])
        df = df.drop_duplicates(subset=["time"])
        df = df.sort_values("time")
        df = df.tail(count)
        df = df.set_index("time")
        df.index.name = "time"
        df = self._validate_df(df)

        if not df.empty:
            self._buffer.set(symbol, timeframe, count, df)

        return df

    async def get_rates_multi(self, symbols: List[str], timeframe: str = "M5",
                               count: int = 500) -> Dict[str, pd.DataFrame]:
        return {
            sym: await self.get_rates(sym, timeframe, count)
            for sym in symbols
        }

    async def get_rates_with_session(
        self, symbol: str, timeframe: str = "M5", count: int = 500,
        dt: Optional[datetime] = None
    ) -> tuple:
        df = await self.get_rates(symbol, timeframe, count)
        analysis = session_manager.analyze(df, dt or datetime.now(timezone.utc))
        return df, analysis

    def get_atr(self, df: pd.DataFrame, period: int = 14) -> Optional[float]:
        if df.empty or len(df) < period + 1:
            return None
        high = df["high"].astype(float)
        low = df["low"].astype(float)
        close = df["close"].astype(float)
        prev_close = close.shift(1)
        tr = pd.concat([
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean().iloc[-1]
        return float(atr) if not pd.isna(atr) else None

    def get_volume_profile(self, df: pd.DataFrame, levels: int = 10) -> Dict[str, float]:
        if df.empty:
            return {}
        high = float(df["high"].max())
        low = float(df["low"].min())
        step = (high - low) / levels
        if step <= 0:
            return {"high": high, "low": low}
        zones = {}
        for i in range(levels):
            zone_low = low + i * step
            zone_high = zone_low + step
            zone_df = df[(df["high"] >= zone_low) & (df["low"] <= zone_high)]
            zones[f"zone_{i}"] = float(zone_df["tick_volume"].sum()) if not zone_df.empty else 0.0
        return zones

    def get_bars_since(self, df: pd.DataFrame, condition_col: str) -> int:
        if condition_col not in df.columns or df.empty:
            return -1
        series = df[condition_col]
        true_indices = series[series == True].index
        if true_indices.empty:
            return -1
        last_true = true_indices[-1]
        return len(df.loc[last_true:]) - 1

    async def has_new_candle(self, symbol: str, timeframe: str = "M5",
                              count: int = 5) -> bool:
        cached = self._buffer.get(symbol, timeframe, count)
        if cached is None or cached.empty:
            return True

        last_cached_time = cached.index[-1]
        df_new = await self.get_rates(symbol, timeframe, count)

        if df_new.empty:
            return False

        last_new_time = df_new.index[-1]
        return last_new_time > last_cached_time

    async def refresh_cache(self, symbol: str, timeframe: str = "M5",
                             count: int = 500) -> pd.DataFrame:
        self._buffer.invalidate(symbol, timeframe)
        return await self.get_rates(symbol, timeframe, count)

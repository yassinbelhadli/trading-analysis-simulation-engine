from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from core_engine.mt_runtime import MTRuntime, MTSymbolInfo


TRADING_HOURS: Dict[str, tuple] = {
    "XAUUSD": ((0, 23, 59), "23h/5d"),
    "NAS100": ((0, 23, 59), "23h/5d"),
    "BTCUSD": ((0, 23, 59), "24h/7d"),
}


@dataclass
class ManagedSymbol:
    name: str
    normalized: str
    digits: int
    point: float
    contract_size: float
    tick_value: float
    tick_size: float
    spread: int
    min_volume: float
    max_volume: float
    volume_step: float
    trade_mode: int
    swap_long: float
    swap_short: float
    trading_hours: str = "23h/5d"
    spread_filter_enabled: bool = True
    max_spread: int = 50
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def spread_in_points(self) -> float:
        return self.spread * self.point if self.point > 0 else self.spread

    @property
    def spread_filter_passed(self) -> bool:
        if not self.spread_filter_enabled:
            return True
        return self.spread <= self.max_spread

    @staticmethod
    def normalize_name(raw: str) -> str:
        from core_engine.data_feed.symbol_resolver import normalize_symbol, resolve_required_markets
        s = raw.upper().strip()
        resolved = resolve_required_markets([s])
        for market in ("GOLD", "NASDAQ", "BITCOIN"):
            r = resolved.get(market)
            if r and r.symbol:
                return r.symbol
        return normalize_symbol(s)


class SymbolManager:
    def __init__(self, runtime: MTRuntime):
        self.runtime = runtime
        self._symbols: Dict[str, ManagedSymbol] = {}
        self._by_normalized: Dict[str, ManagedSymbol] = {}

    async def refresh(self) -> None:
        symbols = await self.runtime.get_symbols()
        self._symbols.clear()
        self._by_normalized.clear()
        for s in symbols:
            norm = ManagedSymbol.normalize_name(s.name)
            managed = ManagedSymbol(
                name=s.name,
                normalized=norm,
                digits=s.digits,
                point=s.point,
                contract_size=s.contract_size,
                tick_value=s.tick_value,
                tick_size=s.tick_size,
                spread=s.spread,
                min_volume=s.min_volume,
                max_volume=s.max_volume,
                volume_step=s.volume_step,
                trade_mode=s.trade_mode,
                swap_long=s.swap_long,
                swap_short=s.swap_short,
                trading_hours=TRADING_HOURS.get(norm, "23h/5d"),
            )
            self._symbols[s.name] = managed
            if norm not in self._by_normalized:
                self._by_normalized[norm] = managed

    def get(self, symbol: str) -> Optional[ManagedSymbol]:
        s = symbol.upper().strip()
        return self._symbols.get(s) or self._by_normalized.get(s)

    def get_normalized(self, normalized: str) -> Optional[ManagedSymbol]:
        return self._by_normalized.get(normalized.upper().strip())

    def all(self) -> List[ManagedSymbol]:
        return list(self._symbols.values())

    def all_normalized(self) -> List[str]:
        return list(self._by_normalized.keys())

    def has(self, symbol: str) -> bool:
        return self.get(symbol) is not None

    def get_spread(self, symbol: str) -> Optional[int]:
        ms = self.get(symbol)
        return ms.spread if ms else None

    def get_tick_value(self, symbol: str) -> Optional[float]:
        ms = self.get(symbol)
        return ms.tick_value if ms else None

    def get_contract_size(self, symbol: str) -> Optional[float]:
        ms = self.get(symbol)
        return ms.contract_size if ms else None

    def is_tradable(self, symbol: str) -> bool:
        ms = self.get(symbol)
        if ms is None:
            return False
        return ms.trade_mode == 0 and ms.spread_filter_passed


symbol_cache: Dict[str, SymbolManager] = {}

"""TradeResult + nested models — the single output object from a simulation run."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional


class TradeOutcome:
    WIN = "WIN"
    LOSS = "LOSS"
    BE = "BREAK_EVEN"
    PENDING = "PENDING"
    EXPIRED = "EXPIRED"
    ERROR = "ERROR"


class TradeState:
    PENDING = "PENDING"
    FILLED = "FILLED"
    TP1_HIT = "TP1_HIT"
    BE_SET = "BE_SET"
    TP2_HIT = "TP2_HIT"
    TRAILING = "TRAILING"
    TP3_HIT = "TP3_HIT"
    CLOSED = "CLOSED"
    STOPPED = "STOPPED"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True)
class TradeEvent:
    time: str              # ISO timestamp or candle time
    state: str             # TradeState value
    price: float
    description: str = ""
    pnl: Optional[float] = None
    rr: Optional[float] = None


@dataclass(frozen=True)
class FillInfo:
    price: float
    time: str
    fill_type: str         # MARKET / LIMIT / STOP
    slippage: float = 0.0
    spread_cost: float = 0.0


@dataclass(frozen=True)
class TradeMetrics:
    total_pnl: float = 0.0
    total_r: float = 0.0
    duration_candles: int = 0
    max_adverse_excursion: float = 0.0
    max_favorable_excursion: float = 0.0
    max_drawdown_pct: float = 0.0
    commission: float = 0.0
    net_pnl: float = 0.0


@dataclass(frozen=True)
class TradeResult:
    """Complete result of a simulated trade — structured, not just win/loss.

    All downstream consumers read this. They never re-simulate.
    """
    outcome: str              # TradeOutcome value
    total_r: float            # realised R multiple
    total_pnl: float          # realised PnL (in account currency)
    events: List[TradeEvent]
    fill: Optional[FillInfo] = None
    plan_id: str = ""
    metrics: Optional[TradeMetrics] = None
    error: str = ""

    @property
    def is_win(self) -> bool:
        return self.outcome == TradeOutcome.WIN

    @property
    def is_loss(self) -> bool:
        return self.outcome == TradeOutcome.LOSS

    @property
    def event_count(self) -> int:
        return len(self.events)

    @property
    def last_event(self) -> Optional[TradeEvent]:
        return self.events[-1] if self.events else None

# partial_close.py
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core_engine.execution.trade_manager import ManagedTrade


@dataclass
class PartialCloseResult:
    applied: bool
    state: str
    reason: str

    trade_id: str
    direction: str

    entry_price: float
    current_price: float
    current_r: float
    trigger_r: float

    old_lot_size: float
    closed_lot_size: float
    remaining_lot_size: float
    close_percent: float

    partial_close_price: float
    partial_pnl_points: float
    partial_pnl_money: float

    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PartialCloseManager:
    def __init__(
        self,
        trigger_r: float = 1.0,
        close_percent: float = 50.0,
        min_remaining_lot: float = 0.01,
        lot_step: float = 0.01,
        contract_size: float = 100.0,
        only_once: bool = True,
    ):
        self.trigger_r = trigger_r
        self.close_percent = close_percent
        self.min_remaining_lot = min_remaining_lot
        self.lot_step = lot_step
        self.contract_size = contract_size
        self.only_once = only_once

    def evaluate(
        self,
        trade: "ManagedTrade",
        current_price: float,
    ) -> PartialCloseResult:

        if trade.status not in ["OPEN", "RUNNING"]:
            return self._result(
                applied=False,
                state="NOT_ACTIVE",
                reason="Trade is not open or running.",
                trade=trade,
                current_price=current_price,
                closed_lot=0.0,
                remaining_lot=trade.lot_size,
                current_r=0.0,
                pnl_points=0.0,
                pnl_money=0.0,
            )

        current_r = self._current_r(trade, current_price)

        if self.only_once and trade.partial_closed:
            return self._result(
                applied=False,
                state="ALREADY_PARTIAL_CLOSED",
                reason="Partial close already applied.",
                trade=trade,
                current_price=current_price,
                closed_lot=0.0,
                remaining_lot=trade.lot_size,
                current_r=current_r,
                pnl_points=0.0,
                pnl_money=0.0,
            )

        if trade.lot_size <= self.min_remaining_lot:
            return self._result(
                applied=False,
                state="LOT_TOO_SMALL",
                reason="Lot size is too small for partial close.",
                trade=trade,
                current_price=current_price,
                closed_lot=0.0,
                remaining_lot=trade.lot_size,
                current_r=current_r,
                pnl_points=0.0,
                pnl_money=0.0,
            )

        if current_r < self.trigger_r:
            return self._result(
                applied=False,
                state="WAITING",
                reason="Partial close trigger not reached.",
                trade=trade,
                current_price=current_price,
                closed_lot=0.0,
                remaining_lot=trade.lot_size,
                current_r=current_r,
                pnl_points=0.0,
                pnl_money=0.0,
            )

        close_percent = max(0.0, min(float(self.close_percent), 100.0))

        raw_closed_lot = trade.lot_size * (close_percent / 100.0)
        closed_lot = self._floor_to_step(raw_closed_lot, self.lot_step)
        remaining_lot = round(trade.lot_size - closed_lot, 4)

        if closed_lot <= 0:
            return self._result(
                applied=False,
                state="INVALID_CLOSED_LOT",
                reason="Closed lot size is invalid after lot step normalization.",
                trade=trade,
                current_price=current_price,
                closed_lot=0.0,
                remaining_lot=trade.lot_size,
                current_r=current_r,
                pnl_points=0.0,
                pnl_money=0.0,
            )

        if remaining_lot < self.min_remaining_lot:
            closed_lot = round(trade.lot_size - self.min_remaining_lot, 4)
            closed_lot = self._floor_to_step(closed_lot, self.lot_step)
            remaining_lot = round(trade.lot_size - closed_lot, 4)

        if closed_lot <= 0 or remaining_lot < self.min_remaining_lot:
            return self._result(
                applied=False,
                state="MIN_REMAINING_LOT_BLOCK",
                reason="Partial close would leave remaining lot below broker minimum.",
                trade=trade,
                current_price=current_price,
                closed_lot=0.0,
                remaining_lot=trade.lot_size,
                current_r=current_r,
                pnl_points=0.0,
                pnl_money=0.0,
            )

        pnl_points = self._pnl_points(trade, current_price)
        pnl_money = self._pnl_money(
            pnl_points=pnl_points,
            closed_lot=closed_lot,
        )

        old_lot = trade.lot_size
        trade.lot_size = round(remaining_lot, 4)
        trade.partial_closed = True

        if trade.metadata is None:
            trade.metadata = {}

        trade.metadata["partial_close"] = {
            "trigger_r": self.trigger_r,
            "close_percent": close_percent,
            "old_lot_size": old_lot,
            "closed_lot_size": closed_lot,
            "remaining_lot_size": trade.lot_size,
            "partial_close_price": current_price,
            "partial_pnl_points": round(pnl_points, 5),
            "partial_pnl_money": round(pnl_money, 2),
        }

        return PartialCloseResult(
            applied=True,
            state="PARTIAL_CLOSED",
            reason="Partial close applied.",
            trade_id=trade.trade_id,
            direction=trade.direction,
            entry_price=trade.entry_price,
            current_price=current_price,
            current_r=round(current_r, 3),
            trigger_r=self.trigger_r,
            old_lot_size=old_lot,
            closed_lot_size=closed_lot,
            remaining_lot_size=trade.lot_size,
            close_percent=close_percent,
            partial_close_price=current_price,
            partial_pnl_points=round(pnl_points, 5),
            partial_pnl_money=round(pnl_money, 2),
            metadata={
                "initial_stop_loss": trade.initial_stop_loss,
                "lot_step": self.lot_step,
                "min_remaining_lot": self.min_remaining_lot,
                "only_once": self.only_once,
            },
        )

    def _current_r(self, trade: "ManagedTrade", current_price: float) -> float:
        risk_distance = abs(trade.entry_price - trade.initial_stop_loss)

        if risk_distance <= 0:
            return 0.0

        if trade.direction == "BUY":
            profit_distance = current_price - trade.entry_price
        elif trade.direction == "SELL":
            profit_distance = trade.entry_price - current_price
        else:
            return 0.0

        return profit_distance / risk_distance

    def _pnl_points(self, trade: "ManagedTrade", current_price: float) -> float:
        if trade.direction == "BUY":
            return current_price - trade.entry_price

        if trade.direction == "SELL":
            return trade.entry_price - current_price

        return 0.0

    def _pnl_money(
        self,
        pnl_points: float,
        closed_lot: float,
    ) -> float:
        return pnl_points * closed_lot * self.contract_size

    def _floor_to_step(self, value: float, step: float) -> float:
        if step <= 0:
            return round(value, 4)

        steps = int(value / step)
        return round(steps * step, 4)

    def _result(
        self,
        applied: bool,
        state: str,
        reason: str,
        trade: "ManagedTrade",
        current_price: float,
        closed_lot: float,
        remaining_lot: float,
        current_r: float,
        pnl_points: float,
        pnl_money: float,
    ) -> PartialCloseResult:

        return PartialCloseResult(
            applied=applied,
            state=state,
            reason=reason,
            trade_id=trade.trade_id,
            direction=trade.direction,
            entry_price=trade.entry_price,
            current_price=current_price,
            current_r=round(current_r, 3),
            trigger_r=self.trigger_r,
            old_lot_size=trade.lot_size,
            closed_lot_size=closed_lot,
            remaining_lot_size=remaining_lot,
            close_percent=self.close_percent,
            partial_close_price=current_price,
            partial_pnl_points=round(pnl_points, 5),
            partial_pnl_money=round(pnl_money, 2),
            metadata=None,
        )

    def should_partial_close(
        self,
        trade: "ManagedTrade",
        current_price: float,
    ) -> bool:
        return self.evaluate(trade, current_price).applied
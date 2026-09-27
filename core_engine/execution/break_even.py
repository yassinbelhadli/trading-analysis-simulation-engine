# break_even.py
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core_engine.execution.trade_manager import ManagedTrade


@dataclass
class BreakEvenResult:
    applied: bool
    state: str
    reason: str

    trade_id: str
    direction: str

    entry_price: float
    old_stop_loss: float
    new_stop_loss: float
    current_price: float

    current_r: float
    trigger_r: float

    lock_profit_points: float
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class BreakEvenManager:
    def __init__(
        self,
        trigger_r: float = 1.0,
        lock_profit_points: float = 0.0,
        only_once: bool = True,
    ):
        self.trigger_r = trigger_r
        self.lock_profit_points = lock_profit_points
        self.only_once = only_once

    def evaluate(
        self,
        trade: "ManagedTrade",
        current_price: float,
    ) -> BreakEvenResult:

        if trade.status not in ["OPEN", "RUNNING"]:
            return self._result(False, "NOT_ACTIVE", "Trade is not open or running.", trade, current_price, trade.stop_loss, 0.0)

        current_r = self._current_r(trade, current_price)

        if self.only_once and trade.be_moved:
            return self._result(False, "ALREADY_MOVED", "Break even already applied.", trade, current_price, trade.stop_loss, current_r)

        risk_distance = abs(trade.entry_price - trade.initial_stop_loss)

        if risk_distance <= 0:
            return self._result(False, "INVALID_RISK", "Invalid initial risk distance.", trade, current_price, trade.stop_loss, 0.0)

        if current_r < self.trigger_r:
            return self._result(False, "WAITING", "Break even trigger not reached.", trade, current_price, trade.stop_loss, current_r)

        if trade.direction == "BUY":
            new_sl = trade.entry_price + self.lock_profit_points

            if new_sl <= trade.stop_loss:
                return self._result(False, "NO_IMPROVEMENT", "New stop loss does not improve current stop loss.", trade, current_price, trade.stop_loss, current_r)

            if new_sl >= current_price:
                return self._result(False, "INVALID_NEW_SL", "New stop loss is above or equal current price.", trade, current_price, trade.stop_loss, current_r)

        elif trade.direction == "SELL":
            new_sl = trade.entry_price - self.lock_profit_points

            if new_sl >= trade.stop_loss:
                return self._result(False, "NO_IMPROVEMENT", "New stop loss does not improve current stop loss.", trade, current_price, trade.stop_loss, current_r)

            if new_sl <= current_price:
                return self._result(False, "INVALID_NEW_SL", "New stop loss is below or equal current price.", trade, current_price, trade.stop_loss, current_r)

        else:
            return self._result(False, "INVALID_DIRECTION", "Invalid trade direction.", trade, current_price, trade.stop_loss, current_r)

        old_sl = trade.stop_loss
        trade.stop_loss = round(new_sl, 5)
        trade.be_moved = True

        return BreakEvenResult(
            applied=True,
            state="BE_MOVED",
            reason="Stop loss moved to break even.",
            trade_id=trade.trade_id,
            direction=trade.direction,
            entry_price=trade.entry_price,
            old_stop_loss=old_sl,
            new_stop_loss=trade.stop_loss,
            current_price=current_price,
            current_r=round(current_r, 3),
            trigger_r=self.trigger_r,
            lock_profit_points=self.lock_profit_points,
            metadata={
                "initial_stop_loss": trade.initial_stop_loss,
                "risk_distance": round(risk_distance, 5),
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

    def _result(
        self,
        applied: bool,
        state: str,
        reason: str,
        trade: "ManagedTrade",
        current_price: float,
        new_sl: float,
        current_r: float,
    ) -> BreakEvenResult:

        return BreakEvenResult(
            applied=applied,
            state=state,
            reason=reason,
            trade_id=trade.trade_id,
            direction=trade.direction,
            entry_price=trade.entry_price,
            old_stop_loss=trade.stop_loss,
            new_stop_loss=new_sl,
            current_price=current_price,
            current_r=round(current_r, 3),
            trigger_r=self.trigger_r,
            lock_profit_points=self.lock_profit_points,
            metadata=None,
        )

    def should_move_to_be(
        self,
        trade: "ManagedTrade",
        current_price: float,
    ) -> bool:
        return self.evaluate(trade, current_price).applied
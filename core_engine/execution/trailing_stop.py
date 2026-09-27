# trailing_stop.py
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, TYPE_CHECKING

import pandas as pd
import numpy as np

if TYPE_CHECKING:
    from core_engine.execution.trade_manager import ManagedTrade


@dataclass
class TrailingStopResult:
    applied: bool
    state: str
    reason: str
    trade_id: str
    direction: str
    entry_price: float
    current_price: float
    old_stop_loss: float
    new_stop_loss: float
    current_r: float
    trigger_r: float
    trailing_method: str
    trailing_distance: float
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TrailingStopManager:
    def __init__(
        self,
        trigger_r: float = 2.0,
        trailing_method: str = "ATR",
        atr_mult: float = 1.5,
        swing_buffer_atr_mult: float = 0.20,
        min_sl_improvement: float = 0.01,
        only_after_be: bool = True,
    ):
        self.trigger_r = trigger_r
        self.trailing_method = str(trailing_method).upper()
        self.atr_mult = atr_mult
        self.swing_buffer_atr_mult = swing_buffer_atr_mult
        self.min_sl_improvement = min_sl_improvement
        self.only_after_be = only_after_be

    def evaluate(
        self,
        trade: "ManagedTrade",
        current_price: float,
        row: Optional[pd.Series] = None,
    ) -> TrailingStopResult:

        if trade.status not in ["OPEN", "RUNNING"]:
            return self._result(False, "NOT_ACTIVE", "Trade is not open or running.", trade, current_price, trade.stop_loss, 0.0, 0.0)

        current_r = self._current_r(trade, current_price)

        if self.only_after_be and not trade.be_moved:
            return self._result(False, "WAITING_BE", "Break-even must be moved before trailing.", trade, current_price, trade.stop_loss, current_r, 0.0)

        if current_r < self.trigger_r:
            return self._result(False, "WAITING", "Trailing trigger not reached.", trade, current_price, trade.stop_loss, current_r, 0.0)

        new_sl = self._calculate_new_sl(trade, current_price, row)

        if new_sl is None or new_sl <= 0:
            return self._result(False, "NO_VALID_TRAIL", "No valid trailing stop found.", trade, current_price, trade.stop_loss, current_r, 0.0)

        old_sl = trade.stop_loss

        if trade.direction == "BUY":
            if new_sl <= old_sl + self.min_sl_improvement:
                return self._result(False, "NO_IMPROVEMENT", "New SL does not improve BUY stop.", trade, current_price, old_sl, current_r, abs(current_price - new_sl))

            if new_sl >= current_price:
                return self._result(False, "INVALID_SL", "BUY trailing SL must be below current price.", trade, current_price, old_sl, current_r, abs(current_price - new_sl))

        elif trade.direction == "SELL":
            if new_sl >= old_sl - self.min_sl_improvement:
                return self._result(False, "NO_IMPROVEMENT", "New SL does not improve SELL stop.", trade, current_price, old_sl, current_r, abs(current_price - new_sl))

            if new_sl <= current_price:
                return self._result(False, "INVALID_SL", "SELL trailing SL must be above current price.", trade, current_price, old_sl, current_r, abs(current_price - new_sl))

        else:
            return self._result(False, "INVALID_DIRECTION", "Invalid trade direction.", trade, current_price, old_sl, current_r, 0.0)

        trade.stop_loss = round(float(new_sl), 5)
        trade.trailing_active = True

        if trade.metadata is None:
            trade.metadata = {}

        trade.metadata["trailing_stop"] = {
            "method": self.trailing_method,
            "trigger_r": self.trigger_r,
            "old_stop_loss": old_sl,
            "new_stop_loss": trade.stop_loss,
            "current_price": current_price,
            "current_r": round(current_r, 3),
            "initial_stop_loss": trade.initial_stop_loss,
        }

        return TrailingStopResult(
            applied=True,
            state="TRAILING_MOVED",
            reason="Trailing stop updated.",
            trade_id=trade.trade_id,
            direction=trade.direction,
            entry_price=trade.entry_price,
            current_price=current_price,
            old_stop_loss=old_sl,
            new_stop_loss=trade.stop_loss,
            current_r=round(current_r, 3),
            trigger_r=self.trigger_r,
            trailing_method=self.trailing_method,
            trailing_distance=round(abs(current_price - trade.stop_loss), 5),
            metadata=trade.metadata["trailing_stop"],
        )

    def _calculate_new_sl(
        self,
        trade: "ManagedTrade",
        current_price: float,
        row: Optional[pd.Series],
    ) -> Optional[float]:

        if self.trailing_method == "ATR":
            return self._atr_trailing(trade, current_price, row)

        if self.trailing_method == "SWING":
            return self._swing_trailing(trade, current_price, row)

        if self.trailing_method == "HYBRID":
            swing_sl = self._swing_trailing(trade, current_price, row)
            atr_sl = self._atr_trailing(trade, current_price, row)

            if swing_sl is None:
                return atr_sl

            if atr_sl is None:
                return swing_sl

            if trade.direction == "BUY":
                return max(swing_sl, atr_sl)

            if trade.direction == "SELL":
                return min(swing_sl, atr_sl)

            return None

        return self._atr_trailing(trade, current_price, row)

    def _atr_trailing(
        self,
        trade: "ManagedTrade",
        current_price: float,
        row: Optional[pd.Series],
    ) -> Optional[float]:

        if row is None:
            return None

        atr = self._safe_float(row.get("ATR", np.nan), np.nan)

        if pd.isna(atr) or atr <= 0:
            return None

        distance = atr * self.atr_mult

        if trade.direction == "BUY":
            return current_price - distance

        if trade.direction == "SELL":
            return current_price + distance

        return None

    def _swing_trailing(
        self,
        trade: "ManagedTrade",
        current_price: float,
        row: Optional[pd.Series],
    ) -> Optional[float]:

        if row is None:
            return None

        atr = self._safe_float(row.get("ATR", 0), 0)
        buffer = atr * self.swing_buffer_atr_mult if atr > 0 else 0

        if trade.direction == "BUY":
            candidates = [
                row.get("Confirmed_Swing_Low", np.nan),
                row.get("Swing_Low", np.nan),
                row.get("Support_Level", np.nan),
                row.get("Low", np.nan),
            ]

            valid = [self._safe_float(x, np.nan) for x in candidates if pd.notna(x)]

            if not valid:
                return None

            return max(valid) - buffer

        if trade.direction == "SELL":
            candidates = [
                row.get("Confirmed_Swing_High", np.nan),
                row.get("Swing_High", np.nan),
                row.get("Resistance_Level", np.nan),
                row.get("High", np.nan),
            ]

            valid = [self._safe_float(x, np.nan) for x in candidates if pd.notna(x)]

            if not valid:
                return None

            return min(valid) + buffer

        return None

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
        trailing_distance: float,
    ) -> TrailingStopResult:

        return TrailingStopResult(
            applied=applied,
            state=state,
            reason=reason,
            trade_id=trade.trade_id,
            direction=trade.direction,
            entry_price=trade.entry_price,
            current_price=current_price,
            old_stop_loss=trade.stop_loss,
            new_stop_loss=new_sl,
            current_r=round(current_r, 3),
            trigger_r=self.trigger_r,
            trailing_method=self.trailing_method,
            trailing_distance=round(trailing_distance, 5),
            metadata=None,
        )

    def _safe_float(self, value, default=0.0) -> float:
        try:
            if pd.isna(value):
                return default
            return float(value)
        except Exception:
            return default
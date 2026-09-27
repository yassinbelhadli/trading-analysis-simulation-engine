# lot_calculator.py
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional
import math

from core_engine.risk.account_profile import AccountProfile


@dataclass
class LotCalculationResult:
    lot_size: float
    raw_lot_size: float
    risk_amount: float
    actual_risk_amount: float
    risk_percent: float
    actual_risk_percent: float

    entry_price: float
    stop_loss_price: float
    take_profit_price: float
    stop_loss_distance: float
    take_profit_distance: float

    rr: float
    direction: str
    symbol: str

    valid: bool
    reason: str
    warning: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class LotCalculator:
    def __init__(
        self,
        default_xau_contract_size=100.0,
        default_forex_pip_value_per_lot=10.0
    ):
        self.default_xau_contract_size = default_xau_contract_size
        self.default_forex_pip_value_per_lot = default_forex_pip_value_per_lot

    def _floor_to_step(self, value: float, step: float) -> float:
        if step <= 0:
            return value
        return math.floor(value / step) * step

    def _normalize_lot(self, lot: float, min_lot: float, max_lot: float, lot_step: float) -> float:
        lot = self._floor_to_step(lot, lot_step)
        lot = max(min_lot, min(lot, max_lot))

        decimals = 2
        if lot_step < 0.01:
            decimals = 3
        if lot_step < 0.001:
            decimals = 4

        return round(lot, decimals)

    def _calculate_tp(self, entry: float, sl: float, direction: str, rr: float) -> float:
        sl_distance = abs(entry - sl)

        if direction == "BUY":
            return entry + (sl_distance * rr)

        if direction == "SELL":
            return entry - (sl_distance * rr)

        return entry

    def _risk_per_1_lot(
        self,
        symbol: str,
        stop_loss_distance: float,
        contract_size: Optional[float] = None,
        tick_value: Optional[float] = None,
        tick_size: Optional[float] = None,
        pip_value_per_lot: Optional[float] = None
    ) -> float:
        symbol = symbol.upper()

        if tick_value is not None and tick_size is not None and tick_size > 0:
            return (stop_loss_distance / tick_size) * tick_value

        if "XAU" in symbol or "GOLD" in symbol:
            cs = contract_size if contract_size is not None else self.default_xau_contract_size
            return stop_loss_distance * cs

        pv = pip_value_per_lot if pip_value_per_lot is not None else self.default_forex_pip_value_per_lot
        return stop_loss_distance * pv

    def calculate_lot(
        self,
        profile: AccountProfile,
        entry_price: float,
        stop_loss_price: float,
        direction: str,
        rr: Optional[float] = None,
        contract_size: Optional[float] = None,
        tick_value: Optional[float] = None,
        tick_size: Optional[float] = None,
        pip_value_per_lot: Optional[float] = None
    ) -> LotCalculationResult:

        direction = direction.upper().strip()
        symbol = profile.symbol.upper()

        if direction not in ["BUY", "SELL"]:
            return self._invalid(profile, entry_price, stop_loss_price, direction, rr, "INVALID_DIRECTION")

        if rr is None:
            rr = profile.preferred_rr

        if rr <= 0:
            return self._invalid(profile, entry_price, stop_loss_price, direction, rr, "INVALID_RR")

        if entry_price <= 0 or stop_loss_price <= 0:
            return self._invalid(profile, entry_price, stop_loss_price, direction, rr, "INVALID_PRICE")

        if direction == "BUY" and stop_loss_price >= entry_price:
            return self._invalid(profile, entry_price, stop_loss_price, direction, rr, "BUY_SL_MUST_BE_BELOW_ENTRY")

        if direction == "SELL" and stop_loss_price <= entry_price:
            return self._invalid(profile, entry_price, stop_loss_price, direction, rr, "SELL_SL_MUST_BE_ABOVE_ENTRY")

        stop_loss_distance = abs(entry_price - stop_loss_price)

        if stop_loss_distance <= 0:
            return self._invalid(profile, entry_price, stop_loss_price, direction, rr, "INVALID_SL_DISTANCE")

        risk_amount = profile.balance * (profile.risk_per_trade / 100)

        risk_per_lot = self._risk_per_1_lot(
            symbol=symbol,
            stop_loss_distance=stop_loss_distance,
            contract_size=contract_size,
            tick_value=tick_value,
            tick_size=tick_size,
            pip_value_per_lot=pip_value_per_lot
        )

        if risk_per_lot <= 0:
            return self._invalid(profile, entry_price, stop_loss_price, direction, rr, "INVALID_RISK_PER_LOT")

        raw_lot = risk_amount / risk_per_lot

        lot = self._normalize_lot(
            raw_lot,
            profile.min_lot,
            profile.max_lot,
            profile.lot_step
        )

        actual_risk_amount = lot * risk_per_lot
        actual_risk_percent = (actual_risk_amount / profile.balance) * 100 if profile.balance > 0 else 0

        take_profit = self._calculate_tp(entry_price, stop_loss_price, direction, rr)
        take_profit_distance = abs(take_profit - entry_price)

        warning = None

        if raw_lot < profile.min_lot:
            warning = "RAW_LOT_BELOW_MIN_LOT"

        if raw_lot > profile.max_lot:
            warning = "RAW_LOT_ABOVE_MAX_LOT"

        if actual_risk_percent > profile.risk_per_trade * 1.25:
            warning = "ACTUAL_RISK_HIGHER_THAN_REQUESTED"

        return LotCalculationResult(
            lot_size=lot,
            raw_lot_size=round(raw_lot, 4),
            risk_amount=round(risk_amount, 2),
            actual_risk_amount=round(actual_risk_amount, 2),
            risk_percent=profile.risk_per_trade,
            actual_risk_percent=round(actual_risk_percent, 4),

            entry_price=round(entry_price, 5),
            stop_loss_price=round(stop_loss_price, 5),
            take_profit_price=round(take_profit, 5),
            stop_loss_distance=round(stop_loss_distance, 5),
            take_profit_distance=round(take_profit_distance, 5),

            rr=rr,
            direction=direction,
            symbol=symbol,

            valid=True,
            reason="OK",
            warning=warning
        )

    def _invalid(self, profile, entry, sl, direction, rr, reason):
        rr = rr if rr is not None else getattr(profile, "preferred_rr", 0)
        return LotCalculationResult(
            lot_size=0.0,
            raw_lot_size=0.0,
            risk_amount=0.0,
            actual_risk_amount=0.0,
            risk_percent=getattr(profile, "risk_per_trade", 0),
            actual_risk_percent=0.0,

            entry_price=entry,
            stop_loss_price=sl,
            take_profit_price=entry,
            stop_loss_distance=abs(entry - sl) if entry and sl else 0,
            take_profit_distance=0.0,

            rr=rr,
            direction=direction,
            symbol=getattr(profile, "symbol", "UNKNOWN"),

            valid=False,
            reason=reason,
            warning=None
        )

    def get_recommended_risk(self, profile: AccountProfile) -> Dict[str, float]:
        account_type = profile.account_type.upper()

        if account_type == "FUNDED":
            return {"risk_per_trade": 0.50, "preferred_rr": 3.0}

        if account_type == "SMALL":
            return {"risk_per_trade": 0.50, "preferred_rr": 2.0}

        return {"risk_per_trade": 1.00, "preferred_rr": 2.5}

    def calculation_summary(self, result: LotCalculationResult) -> Dict[str, Any]:
        return result.to_dict()
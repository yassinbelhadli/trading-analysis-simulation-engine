from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from core_engine.detection.setup_detector import SetupCandidate
from core_engine.risk.account_profile import AccountProfile
from core_engine.risk.lot_calculator import LotCalculator, LotCalculationResult
from core_engine.risk.risk_validator import RiskValidator, RiskValidationResult


@dataclass
class TradePlan:
    valid: bool
    symbol: str
    direction: str
    entry_type: str
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_reward: float
    lot_size: float
    risk_percent: float
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class PlanValidation:
    valid: bool
    risk_ok: bool
    entry_ok: bool
    rr_ok: bool
    validation_result: Optional[RiskValidationResult] = None
    lot_result: Optional[LotCalculationResult] = None
    warnings: List[str] = field(default_factory=list)


class TradePlanner:
    def __init__(
        self,
        lot_calculator: Optional[LotCalculator] = None,
        risk_validator: Optional[RiskValidator] = None,
        default_rr: float = 2.0,
        min_rr: float = 1.5,
    ):
        self.lot_calculator = lot_calculator or LotCalculator()
        self.risk_validator = risk_validator or RiskValidator()
        self.default_rr = default_rr
        self.min_rr = min_rr

    def plan(
        self,
        candidate: SetupCandidate,
        profile: AccountProfile,
        current_price: Optional[float] = None,
        rr: Optional[float] = None,
    ) -> TradePlan:
        if not candidate.structure.valid:
            return self._invalid(candidate.symbol, candidate.direction, "NO_STRUCTURE")

        direction = candidate.direction
        rr = rr or profile.preferred_rr or self.default_rr

        entry_price, stop_loss = self._calculate_entry_and_sl(candidate, direction, current_price)
        if entry_price is None or stop_loss is None:
            return self._invalid(candidate.symbol, direction, "COULD_NOT_DETERMINE_ENTRY_SL")

        take_profit = self._calculate_tp(entry_price, stop_loss, direction, rr)
        sl_distance = abs(entry_price - stop_loss)

        profile_adj = self._build_profile_for_symbol(profile, candidate.symbol)
        lot_result = self.lot_calculator.calculate_lot(
            profile=profile_adj,
            entry_price=entry_price,
            stop_loss_price=stop_loss,
            direction=direction,
            rr=rr,
        )

        warnings: List[str] = []
        if lot_result.warning:
            warnings.append(lot_result.warning)

        if lot_result.rr < self.min_rr:
            warnings.append(f"R_R_BELOW_MINIMUM: {lot_result.rr:.2f}")

        actual_rr = lot_result.rr

        reasons = self._collect_plan_reasons(candidate, entry_price, stop_loss, take_profit, actual_rr)

        if lot_result.valid:
            return TradePlan(
                valid=True,
                symbol=candidate.symbol,
                direction=direction,
                entry_type="MARKET",
                entry_price=lot_result.entry_price,
                stop_loss=lot_result.stop_loss_price,
                take_profit=lot_result.take_profit_price,
                risk_reward=actual_rr,
                lot_size=lot_result.lot_size,
                risk_percent=lot_result.actual_risk_percent,
                reasons=reasons,
                warnings=warnings,
            )

        return self._invalid(candidate.symbol, direction, lot_result.reason, warnings)

    def _calculate_entry_and_sl(
        self,
        candidate: SetupCandidate,
        direction: str,
        current_price: Optional[float] = None,
    ):
        entry = None
        sl = None

        if direction == "BUY":
            if candidate.ob and candidate.ob.ob_detected and not candidate.ob.mitigated:
                if candidate.ob.ob_mid:
                    entry = candidate.ob.ob_mid
                elif candidate.ob.ob_top:
                    entry = candidate.ob.ob_top
                if candidate.ob.ob_bottom:
                    sl = candidate.ob.ob_bottom
            elif candidate.fvg and candidate.fvg.fvg_detected and not candidate.fvg.mitigated:
                if candidate.fvg.fvg_top and candidate.fvg.fvg_bottom:
                    entry = (candidate.fvg.fvg_top + candidate.fvg.fvg_bottom) / 2
                    sl = candidate.fvg.fvg_bottom
            if entry is None:
                entry = current_price
            if sl is None and candidate.structure.protected_low:
                sl = candidate.structure.protected_low
            if sl is None and current_price:
                sl = current_price * 0.995

        elif direction == "SELL":
            if candidate.ob and candidate.ob.ob_detected and not candidate.ob.mitigated:
                if candidate.ob.ob_mid:
                    entry = candidate.ob.ob_mid
                elif candidate.ob.ob_bottom:
                    entry = candidate.ob.ob_bottom
                if candidate.ob.ob_top:
                    sl = candidate.ob.ob_top
            elif candidate.fvg and candidate.fvg.fvg_detected and not candidate.fvg.mitigated:
                if candidate.fvg.fvg_top and candidate.fvg.fvg_bottom:
                    entry = (candidate.fvg.fvg_top + candidate.fvg.fvg_bottom) / 2
                    sl = candidate.fvg.fvg_top
            if entry is None:
                entry = current_price
            if sl is None and candidate.structure.protected_high:
                sl = candidate.structure.protected_high
            if sl is None and current_price:
                sl = current_price * 1.005

        if entry is not None and sl is not None:
            if direction == "BUY" and sl >= entry:
                if candidate.structure.protected_low:
                    sl = candidate.structure.protected_low
                else:
                    sl = entry * 0.995
            if direction == "SELL" and sl <= entry:
                if candidate.structure.protected_high:
                    sl = candidate.structure.protected_high
                else:
                    sl = entry * 1.005

        return entry, sl

    def _calculate_tp(self, entry: float, sl: float, direction: str, rr: float) -> float:
        sl_distance = abs(entry - sl)
        if direction == "BUY":
            return entry + (sl_distance * rr)
        return entry - (sl_distance * rr)

    def _build_profile_for_symbol(self, profile: AccountProfile, symbol: str) -> AccountProfile:
        import copy
        adjusted = copy.copy(profile)
        adjusted.symbol = symbol.upper()
        return adjusted

    def _collect_plan_reasons(
        self, candidate: SetupCandidate,
        entry: float, sl: float, tp: float, rr: float,
    ) -> List[str]:
        reasons = []
        if candidate.ob and candidate.ob.ob_detected:
            reasons.append(f"Entry_Based_On_{candidate.ob.ob_type}_OB")
        if candidate.fvg and candidate.fvg.fvg_detected:
            reasons.append("Entry_Based_On_FVG")
        if candidate.score_result and candidate.score_result.recommendation == "EXECUTE":
            reasons.append("Score_Recommended_Execute")
        reasons.append(f"RR_{rr:.1f}")
        return reasons

    def _invalid(
        self, symbol: str, direction: str, reason: str,
        warnings: Optional[List[str]] = None,
    ) -> TradePlan:
        return TradePlan(
            valid=False,
            symbol=symbol,
            direction=direction,
            entry_type="NONE",
            entry_price=0.0,
            stop_loss=0.0,
            take_profit=0.0,
            risk_reward=0.0,
            lot_size=0.0,
            risk_percent=0.0,
            reasons=[reason],
            warnings=warnings or [],
        )

    def validate_plan(self, plan: TradePlan) -> PlanValidation:
        warnings: List[str] = []

        risk_ok = True
        if plan.risk_percent > 2.0:
            risk_ok = False
            warnings.append("RISK_PERCENT_TOO_HIGH")

        entry_ok = plan.entry_price > 0
        if not entry_ok:
            warnings.append("INVALID_ENTRY_PRICE")

        rr_ok = plan.risk_reward >= self.min_rr
        if not rr_ok:
            warnings.append(f"R_R_TOO_LOW: {plan.risk_reward:.2f}")

        return PlanValidation(
            valid=risk_ok and entry_ok and rr_ok and plan.valid,
            risk_ok=risk_ok,
            entry_ok=entry_ok,
            rr_ok=rr_ok,
            warnings=warnings,
        )

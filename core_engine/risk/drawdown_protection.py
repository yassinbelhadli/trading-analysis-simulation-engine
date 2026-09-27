# drawdown_protection.py
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional

from core_engine.risk.account_profile import AccountProfile


@dataclass
class DrawdownProtectionResult:
    allowed: bool
    state: str
    reason: str

    start_balance: float
    peak_equity: float
    current_equity: float

    absolute_drawdown_amount: float
    absolute_drawdown_percent: float

    floating_drawdown_amount: float
    floating_drawdown_percent: float

    original_risk_percent: float
    adjusted_risk_percent: float
    risk_multiplier: float

    recommended_action: str
    warning: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DrawdownProtection:
    def __init__(
        self,
        dd_warning_level=3.0,
        dd_reduce_level=5.0,
        dd_defensive_level=7.0,
        dd_hard_stop_level=9.0,
        min_risk_percent=0.10
    ):
        self.dd_warning_level = dd_warning_level
        self.dd_reduce_level = dd_reduce_level
        self.dd_defensive_level = dd_defensive_level
        self.dd_hard_stop_level = dd_hard_stop_level
        self.min_risk_percent = min_risk_percent

    def evaluate(
        self,
        profile: AccountProfile,
        current_equity: float,
        start_balance: Optional[float] = None,
        peak_equity: Optional[float] = None
    ) -> DrawdownProtectionResult:

        if start_balance is None:
            start_balance = profile.balance

        if peak_equity is None:
            peak_equity = max(start_balance, current_equity)

        if start_balance <= 0:
            return DrawdownProtectionResult(
                allowed=False,
                state="INVALID_START_BALANCE",
                reason="Start balance must be greater than 0.",
                start_balance=start_balance,
                peak_equity=peak_equity,
                current_equity=current_equity,
                absolute_drawdown_amount=0.0,
                absolute_drawdown_percent=0.0,
                floating_drawdown_amount=0.0,
                floating_drawdown_percent=0.0,
                original_risk_percent=profile.risk_per_trade,
                adjusted_risk_percent=0.0,
                risk_multiplier=0.0,
                recommended_action="BLOCK_TRADING",
                warning="Invalid account state.",
            )

        if current_equity <= 0:
            return DrawdownProtectionResult(
                allowed=False,
                state="INVALID_EQUITY",
                reason="Current equity must be greater than 0.",
                start_balance=start_balance,
                peak_equity=peak_equity,
                current_equity=current_equity,
                absolute_drawdown_amount=0.0,
                absolute_drawdown_percent=0.0,
                floating_drawdown_amount=0.0,
                floating_drawdown_percent=0.0,
                original_risk_percent=profile.risk_per_trade,
                adjusted_risk_percent=0.0,
                risk_multiplier=0.0,
                recommended_action="BLOCK_TRADING",
                warning="Invalid account state.",
            )

        absolute_dd_amount = max(0.0, start_balance - current_equity)
        absolute_dd_percent = (absolute_dd_amount / start_balance) * 100

        floating_dd_amount = max(0.0, peak_equity - current_equity)
        floating_dd_percent = (floating_dd_amount / peak_equity) * 100 if peak_equity > 0 else 0.0

        effective_dd = max(absolute_dd_percent, floating_dd_percent)

        allowed = True
        state = "SAFE"
        reason = "OK"
        action = "ALLOW_TRADING"
        warning = None
        risk_multiplier = 1.0

        if effective_dd >= self.dd_hard_stop_level:
            allowed = False
            state = "DRAWDOWN_HARD_STOP"
            reason = "Drawdown is too high. Trading should stop."
            action = "STOP_TRADING"
            warning = "Drawdown hard stop triggered."
            risk_multiplier = 0.0

        elif effective_dd >= self.dd_defensive_level:
            state = "DEFENSIVE_MODE"
            reason = "Drawdown is high. Defensive mode enabled."
            action = "TRADE_ONLY_ELITE_SETUPS"
            warning = "Trade only the best setups with minimum risk."
            risk_multiplier = 0.25

        elif effective_dd >= self.dd_reduce_level:
            state = "REDUCE_RISK"
            reason = "Drawdown is elevated. Risk reduction enabled."
            action = "REDUCE_RISK"
            warning = "Risk reduced due to drawdown."
            risk_multiplier = 0.50

        elif effective_dd >= self.dd_warning_level:
            state = "DRAWDOWN_WARNING"
            reason = "Drawdown is approaching risk reduction zone."
            action = "TRADE_WITH_CAUTION"
            warning = "Drawdown warning."
            risk_multiplier = 0.75

        adjusted_risk = profile.risk_per_trade * risk_multiplier

        if allowed:
            adjusted_risk = max(self.min_risk_percent, adjusted_risk)
        else:
            adjusted_risk = 0.0

        return DrawdownProtectionResult(
            allowed=allowed,
            state=state,
            reason=reason,

            start_balance=round(start_balance, 2),
            peak_equity=round(peak_equity, 2),
            current_equity=round(current_equity, 2),

            absolute_drawdown_amount=round(absolute_dd_amount, 2),
            absolute_drawdown_percent=round(absolute_dd_percent, 2),

            floating_drawdown_amount=round(floating_dd_amount, 2),
            floating_drawdown_percent=round(floating_dd_percent, 2),

            original_risk_percent=round(profile.risk_per_trade, 4),
            adjusted_risk_percent=round(adjusted_risk, 4),
            risk_multiplier=round(risk_multiplier, 2),

            recommended_action=action,
            warning=warning,
        )

    def get_adjusted_risk_percent(
        self,
        profile: AccountProfile,
        current_equity: float,
        start_balance: Optional[float] = None,
        peak_equity: Optional[float] = None
    ) -> float:
        result = self.evaluate(
            profile=profile,
            current_equity=current_equity,
            start_balance=start_balance,
            peak_equity=peak_equity
        )

        return result.adjusted_risk_percent

    def can_open_trade(
        self,
        profile: AccountProfile,
        current_equity: float,
        start_balance: Optional[float] = None,
        peak_equity: Optional[float] = None
    ) -> bool:
        result = self.evaluate(
            profile=profile,
            current_equity=current_equity,
            start_balance=start_balance,
            peak_equity=peak_equity
        )

        return result.allowed
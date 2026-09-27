# daily_loss_guard.py
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional

from core_engine.risk.account_profile import AccountProfile


@dataclass
class DailyLossGuardResult:
    allowed: bool
    state: str
    reason: str

    daily_start_equity: float
    current_equity: float

    daily_loss_amount: float
    daily_loss_percent: float

    max_daily_loss_percent: float
    max_daily_loss_amount: float

    remaining_daily_loss_amount: float

    planned_risk_amount: float
    projected_daily_loss_amount: float
    projected_daily_loss_percent: float

    recommended_action: str
    warning: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DailyLossGuard:
    def __init__(
        self,
        warning_buffer=0.70,
        reduce_risk_buffer=0.85,
        hard_stop_buffer=0.95
    ):
        self.warning_buffer = warning_buffer
        self.reduce_risk_buffer = reduce_risk_buffer
        self.hard_stop_buffer = hard_stop_buffer

    def evaluate(
        self,
        profile: AccountProfile,
        current_equity: float,
        daily_start_equity: float,
        planned_risk_amount: float = 0.0
    ) -> DailyLossGuardResult:

        max_daily_loss_amount = daily_start_equity * (profile.max_daily_loss / 100)

        current_daily_loss = max(0.0, daily_start_equity - current_equity)
        projected_daily_loss = current_daily_loss + max(0.0, planned_risk_amount)

        daily_loss_percent = (
            current_daily_loss / daily_start_equity * 100
            if daily_start_equity > 0 else 0.0
        )

        projected_daily_loss_percent = (
            projected_daily_loss / daily_start_equity * 100
            if daily_start_equity > 0 else 0.0
        )

        remaining_daily_loss = max(0.0, max_daily_loss_amount - projected_daily_loss)

        allowed = True
        state = "SAFE"
        reason = "OK"
        action = "ALLOW_TRADING"
        warning = None

        if daily_start_equity <= 0:
            return DailyLossGuardResult(
                allowed=False,
                state="INVALID_DAILY_START_EQUITY",
                reason="Daily start equity must be greater than 0.",
                daily_start_equity=daily_start_equity,
                current_equity=current_equity,
                daily_loss_amount=0.0,
                daily_loss_percent=0.0,
                max_daily_loss_percent=profile.max_daily_loss,
                max_daily_loss_amount=0.0,
                remaining_daily_loss_amount=0.0,
                planned_risk_amount=planned_risk_amount,
                projected_daily_loss_amount=0.0,
                projected_daily_loss_percent=0.0,
                recommended_action="BLOCK_TRADING",
                warning="Invalid account state.",
            )

        if projected_daily_loss >= max_daily_loss_amount * self.hard_stop_buffer:
            allowed = False
            state = "DAILY_HARD_STOP"
            reason = "Projected daily loss is too close to the daily loss limit."
            action = "STOP_TRADING_FOR_TODAY"
            warning = "Daily loss protection triggered."

        elif projected_daily_loss >= max_daily_loss_amount * self.reduce_risk_buffer:
            allowed = True
            state = "DAILY_REDUCE_RISK"
            reason = "Projected daily loss is near daily loss limit."
            action = "REDUCE_RISK_OR_SKIP"
            warning = "Risk should be reduced aggressively."

        elif projected_daily_loss >= max_daily_loss_amount * self.warning_buffer:
            allowed = True
            state = "DAILY_WARNING"
            reason = "Daily loss is approaching the warning zone."
            action = "TRADE_WITH_CAUTION"
            warning = "Be careful. Daily risk budget is getting low."

        return DailyLossGuardResult(
            allowed=allowed,
            state=state,
            reason=reason,

            daily_start_equity=round(daily_start_equity, 2),
            current_equity=round(current_equity, 2),

            daily_loss_amount=round(current_daily_loss, 2),
            daily_loss_percent=round(daily_loss_percent, 2),

            max_daily_loss_percent=profile.max_daily_loss,
            max_daily_loss_amount=round(max_daily_loss_amount, 2),

            remaining_daily_loss_amount=round(remaining_daily_loss, 2),

            planned_risk_amount=round(planned_risk_amount, 2),
            projected_daily_loss_amount=round(projected_daily_loss, 2),
            projected_daily_loss_percent=round(projected_daily_loss_percent, 2),

            recommended_action=action,
            warning=warning,
        )

    def can_open_trade(
        self,
        profile: AccountProfile,
        current_equity: float,
        daily_start_equity: float,
        planned_risk_amount: float = 0.0
    ) -> bool:
        result = self.evaluate(
            profile=profile,
            current_equity=current_equity,
            daily_start_equity=daily_start_equity,
            planned_risk_amount=planned_risk_amount
        )

        return result.allowed
# max_loss_guard.py
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional

from core_engine.risk.account_profile import AccountProfile


@dataclass
class MaxLossGuardResult:
    allowed: bool
    state: str
    reason: str

    start_balance: float
    current_equity: float

    total_loss_amount: float
    total_loss_percent: float

    max_account_loss_percent: float
    max_account_loss_amount: float

    remaining_account_loss_amount: float

    planned_risk_amount: float
    projected_total_loss_amount: float
    projected_total_loss_percent: float

    recommended_action: str
    warning: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MaxLossGuard:
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
        start_balance: Optional[float] = None,
        planned_risk_amount: float = 0.0
    ) -> MaxLossGuardResult:

        if start_balance is None:
            start_balance = profile.balance

        if start_balance <= 0:
            return MaxLossGuardResult(
                allowed=False,
                state="INVALID_START_BALANCE",
                reason="Start balance must be greater than 0.",
                start_balance=start_balance,
                current_equity=current_equity,
                total_loss_amount=0.0,
                total_loss_percent=0.0,
                max_account_loss_percent=profile.max_account_loss,
                max_account_loss_amount=0.0,
                remaining_account_loss_amount=0.0,
                planned_risk_amount=planned_risk_amount,
                projected_total_loss_amount=0.0,
                projected_total_loss_percent=0.0,
                recommended_action="BLOCK_TRADING",
                warning="Invalid account state.",
            )

        max_account_loss_amount = start_balance * (profile.max_account_loss / 100)

        current_total_loss = max(0.0, start_balance - current_equity)
        projected_total_loss = current_total_loss + max(0.0, planned_risk_amount)

        total_loss_percent = (current_total_loss / start_balance) * 100
        projected_total_loss_percent = (projected_total_loss / start_balance) * 100

        remaining_account_loss = max(0.0, max_account_loss_amount - projected_total_loss)

        allowed = True
        state = "SAFE"
        reason = "OK"
        action = "ALLOW_TRADING"
        warning = None

        if projected_total_loss >= max_account_loss_amount * self.hard_stop_buffer:
            allowed = False
            state = "MAX_LOSS_HARD_STOP"
            reason = "Projected total loss is too close to the maximum account loss limit."
            action = "STOP_TRADING_ACCOUNT"
            warning = "Maximum account loss protection triggered."

        elif projected_total_loss >= max_account_loss_amount * self.reduce_risk_buffer:
            allowed = True
            state = "MAX_LOSS_REDUCE_RISK"
            reason = "Projected total loss is near maximum account loss limit."
            action = "REDUCE_RISK_OR_SKIP"
            warning = "Risk should be reduced aggressively."

        elif projected_total_loss >= max_account_loss_amount * self.warning_buffer:
            allowed = True
            state = "MAX_LOSS_WARNING"
            reason = "Total account loss is approaching the warning zone."
            action = "TRADE_WITH_CAUTION"
            warning = "Account risk budget is getting low."

        return MaxLossGuardResult(
            allowed=allowed,
            state=state,
            reason=reason,

            start_balance=round(start_balance, 2),
            current_equity=round(current_equity, 2),

            total_loss_amount=round(current_total_loss, 2),
            total_loss_percent=round(total_loss_percent, 2),

            max_account_loss_percent=profile.max_account_loss,
            max_account_loss_amount=round(max_account_loss_amount, 2),

            remaining_account_loss_amount=round(remaining_account_loss, 2),

            planned_risk_amount=round(planned_risk_amount, 2),
            projected_total_loss_amount=round(projected_total_loss, 2),
            projected_total_loss_percent=round(projected_total_loss_percent, 2),

            recommended_action=action,
            warning=warning,
        )

    def can_open_trade(
        self,
        profile: AccountProfile,
        current_equity: float,
        start_balance: Optional[float] = None,
        planned_risk_amount: float = 0.0
    ) -> bool:
        result = self.evaluate(
            profile=profile,
            current_equity=current_equity,
            start_balance=start_balance,
            planned_risk_amount=planned_risk_amount
        )

        return result.allowed
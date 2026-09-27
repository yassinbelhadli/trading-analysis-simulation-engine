# funded_risk.py
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional

from core_engine.risk.account_profile import AccountProfile


@dataclass
class FundedRiskResult:
    allowed: bool
    risk_state: str
    reason: str

    balance: float
    equity: float
    start_balance: float

    daily_start_equity: float
    daily_loss_amount: float
    daily_loss_percent: float

    total_loss_amount: float
    total_loss_percent: float

    max_daily_loss_percent: float
    max_account_loss_percent: float

    remaining_daily_loss_amount: float
    remaining_total_loss_amount: float

    recommended_action: str
    warning: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class FundedRiskManager:
    def __init__(
        self,
        daily_warning_buffer=0.75,
        total_warning_buffer=0.80,
        hard_stop_buffer=0.95
    ):
        self.daily_warning_buffer = daily_warning_buffer
        self.total_warning_buffer = total_warning_buffer
        self.hard_stop_buffer = hard_stop_buffer

    def evaluate(
        self,
        profile: AccountProfile,
        current_equity: float,
        daily_start_equity: float,
        start_balance: Optional[float] = None,
        open_trade_risk_amount: float = 0.0,
    ) -> FundedRiskResult:

        if start_balance is None:
            start_balance = profile.balance

        max_daily_loss_amount = daily_start_equity * (profile.max_daily_loss / 100)
        max_account_loss_amount = start_balance * (profile.max_account_loss / 100)

        daily_loss_amount = max(0.0, daily_start_equity - current_equity)
        total_loss_amount = max(0.0, start_balance - current_equity)

        projected_daily_loss = daily_loss_amount + open_trade_risk_amount
        projected_total_loss = total_loss_amount + open_trade_risk_amount

        daily_loss_percent = (
            projected_daily_loss / daily_start_equity * 100
            if daily_start_equity > 0 else 0
        )

        total_loss_percent = (
            projected_total_loss / start_balance * 100
            if start_balance > 0 else 0
        )

        remaining_daily = max(0.0, max_daily_loss_amount - projected_daily_loss)
        remaining_total = max(0.0, max_account_loss_amount - projected_total_loss)

        allowed = True
        risk_state = "SAFE"
        reason = "OK"
        warning = None
        action = "ALLOW_TRADING"

        if profile.account_type.upper() != "FUNDED":
            return FundedRiskResult(
                allowed=True,
                risk_state="NOT_FUNDED",
                reason="Account is not funded. Funded rules not enforced.",
                balance=profile.balance,
                equity=current_equity,
                start_balance=start_balance,
                daily_start_equity=daily_start_equity,
                daily_loss_amount=round(projected_daily_loss, 2),
                daily_loss_percent=round(daily_loss_percent, 2),
                total_loss_amount=round(projected_total_loss, 2),
                total_loss_percent=round(total_loss_percent, 2),
                max_daily_loss_percent=profile.max_daily_loss,
                max_account_loss_percent=profile.max_account_loss,
                remaining_daily_loss_amount=round(remaining_daily, 2),
                remaining_total_loss_amount=round(remaining_total, 2),
                recommended_action="ALLOW_TRADING",
                warning=None,
            )

        if projected_daily_loss >= max_daily_loss_amount * self.hard_stop_buffer:
            allowed = False
            risk_state = "DAILY_HARD_STOP"
            reason = "Projected daily loss is too close to or above funded daily loss limit."
            action = "STOP_TRADING_FOR_TODAY"

        elif projected_total_loss >= max_account_loss_amount * self.hard_stop_buffer:
            allowed = False
            risk_state = "TOTAL_HARD_STOP"
            reason = "Projected total loss is too close to or above funded max account loss limit."
            action = "STOP_TRADING_ACCOUNT"

        elif projected_daily_loss >= max_daily_loss_amount * self.daily_warning_buffer:
            risk_state = "DAILY_WARNING"
            reason = "Projected daily loss is near daily funded limit."
            warning = "Reduce risk or stop trading for today."
            action = "REDUCE_RISK"

        elif projected_total_loss >= max_account_loss_amount * self.total_warning_buffer:
            risk_state = "TOTAL_WARNING"
            reason = "Projected total loss is near max account loss limit."
            warning = "Reduce risk aggressively."
            action = "REDUCE_RISK"

        return FundedRiskResult(
            allowed=allowed,
            risk_state=risk_state,
            reason=reason,
            balance=profile.balance,
            equity=current_equity,
            start_balance=start_balance,
            daily_start_equity=daily_start_equity,
            daily_loss_amount=round(projected_daily_loss, 2),
            daily_loss_percent=round(daily_loss_percent, 2),
            total_loss_amount=round(projected_total_loss, 2),
            total_loss_percent=round(total_loss_percent, 2),
            max_daily_loss_percent=profile.max_daily_loss,
            max_account_loss_percent=profile.max_account_loss,
            remaining_daily_loss_amount=round(remaining_daily, 2),
            remaining_total_loss_amount=round(remaining_total, 2),
            recommended_action=action,
            warning=warning,
        )

    def can_open_trade(
        self,
        profile: AccountProfile,
        current_equity: float,
        daily_start_equity: float,
        planned_risk_amount: float,
        start_balance: Optional[float] = None,
    ) -> bool:
        result = self.evaluate(
            profile=profile,
            current_equity=current_equity,
            daily_start_equity=daily_start_equity,
            start_balance=start_balance,
            open_trade_risk_amount=planned_risk_amount,
        )

        return result.allowed
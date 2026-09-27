from datetime import datetime, timezone, date
from dataclasses import dataclass, asdict
from decimal import Decimal
from typing import Optional, List, Dict, Any
import json

from sqlalchemy.ext.asyncio import AsyncSession

from database.models import TradingAccount, RiskProfile
from database.repositories import AccountRepository
from core_engine.risk.account_profile import AccountProfile, AccountProfileBuilder
from core_engine.risk.funded_risk import FundedRiskManager, FundedRiskResult
from core_engine.risk.daily_loss_guard import DailyLossGuard, DailyLossGuardResult
from core_engine.risk.max_loss_guard import MaxLossGuard, MaxLossGuardResult
from core_engine.risk.drawdown_protection import DrawdownProtection, DrawdownProtectionResult
from core_engine.risk.risk_validator import RiskValidator, RiskValidationResult
from core_engine.risk.lot_calculator import LotCalculator, LotCalculationResult
from core_engine.account_manager import AccountNotFoundError


class AccountNotActiveError(Exception):
    pass


class RiskProfileNotFoundError(Exception):
    pass


class RiskBreachError(Exception):
    def __init__(self, breaches: List[Dict[str, Any]]):
        self.breaches = breaches
        super().__init__(f"Risk breach: {[b['type'] for b in breaches]}")


# ---------------------------------------------------------------------------
# Guard result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ProfitTargetResult:
    allowed: bool
    reason: str
    profit_amount: float
    profit_percent: float
    profit_target_percent: float
    start_balance: float
    current_equity: float
    warning: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MinTradingDaysResult:
    allowed: bool
    reason: str
    min_trading_days: int
    trading_days_count: int
    days_remaining: int
    warning: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# RiskManager
# ---------------------------------------------------------------------------

class RiskManager:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.acc_repo = AccountRepository(session)
        self.profile_builder = AccountProfileBuilder()
        self.risk_validator = RiskValidator()
        self.lot_calculator = LotCalculator()
        self.funded_risk = FundedRiskManager()
        self.daily_guard = DailyLossGuard()
        self.max_loss_guard = MaxLossGuard()
        self.drawdown_protection = DrawdownProtection()

    async def _load_account(self, account_id: str) -> TradingAccount:
        from sqlalchemy import select as sa_select
        from sqlalchemy.orm import selectinload
        stmt = (
            sa_select(TradingAccount)
            .options(selectinload(TradingAccount.risk_profile))
            .where(TradingAccount.id == account_id)
        )
        result = await self.session.execute(stmt)
        account = result.scalar_one_or_none()
        if not account:
            raise AccountNotFoundError(f"Account {account_id} not found")
        return account

    def _build_profile(self, account: TradingAccount) -> AccountProfile:
        risk: Optional[RiskProfile] = account.risk_profile
        balance = account.balance_snapshot or account.account_size or 0.0

        if risk:
            mode_map = {"ultra_conservative": 0.10, "conservative": 0.25, "balanced": 0.50, "aggressive": 1.0}
            risk_pct = float(risk.max_risk_trade) if risk.max_risk_trade else mode_map.get(risk.mode or "balanced", 0.5)
            custom_settings = {
                "risk_per_trade": risk_pct,
                "max_daily_loss": float(risk.daily_loss) if risk.daily_loss else 3.0,
                "max_account_loss": float(risk.max_loss) if risk.max_loss else 10.0,
            }
        else:
            custom_settings = None

        return self.profile_builder.create_profile(
            client_id=account.id,
            account_type=account.account_type or "PERSONAL",
            balance=float(balance),
            equity=float(account.equity_snapshot or balance),
            broker=account.broker,
            prop_firm=account.prop_firm,
            currency=account.currency or "USD",
            use_recommended_settings=not bool(risk),
            custom_settings_acknowledged=False,
            custom_settings=custom_settings,
            min_trading_days=risk.min_trading_days if risk else None,
            profit_target=risk.profit_target if risk else None,
            trading_days_count=risk.trading_days_count if risk else 0,
            first_trade_date=risk.first_trade_date.isoformat() if risk and risk.first_trade_date else None,
        )

    async def validate_risk_profile(self, account_id: str) -> RiskValidationResult:
        account = await self._load_account(account_id)
        profile = self._build_profile(account)
        return self.risk_validator.validate_profile(profile)

    async def evaluate_funded_risk(
        self,
        account_id: str,
        current_equity: float,
        daily_start_equity: Optional[float] = None,
        start_balance: Optional[float] = None,
        open_trade_risk_amount: float = 0.0,
    ) -> FundedRiskResult:
        account = await self._load_account(account_id)
        profile = self._build_profile(account)
        if daily_start_equity is None:
            daily_start_equity = current_equity
        if start_balance is None:
            start_balance = profile.balance
        return self.funded_risk.evaluate(
            profile=profile,
            current_equity=current_equity,
            daily_start_equity=daily_start_equity,
            start_balance=start_balance,
            open_trade_risk_amount=open_trade_risk_amount,
        )

    async def check_daily_loss(
        self,
        account_id: str,
        current_equity: float,
        daily_start_equity: float,
        planned_risk_amount: float = 0.0,
    ) -> DailyLossGuardResult:
        account = await self._load_account(account_id)
        profile = self._build_profile(account)
        return self.daily_guard.evaluate(
            profile=profile,
            current_equity=current_equity,
            daily_start_equity=daily_start_equity,
            planned_risk_amount=planned_risk_amount,
        )

    async def check_max_loss(
        self,
        account_id: str,
        current_equity: float,
        start_balance: Optional[float] = None,
        planned_risk_amount: float = 0.0,
    ) -> MaxLossGuardResult:
        account = await self._load_account(account_id)
        profile = self._build_profile(account)
        if start_balance is None:
            start_balance = profile.balance
        return self.max_loss_guard.evaluate(
            profile=profile,
            current_equity=current_equity,
            start_balance=start_balance,
            planned_risk_amount=planned_risk_amount,
        )

    async def check_drawdown(
        self,
        account_id: str,
        current_equity: float,
        start_balance: Optional[float] = None,
        peak_equity: Optional[float] = None,
    ) -> DrawdownProtectionResult:
        account = await self._load_account(account_id)
        profile = self._build_profile(account)
        if start_balance is None:
            start_balance = profile.balance
        return self.drawdown_protection.evaluate(
            profile=profile,
            current_equity=current_equity,
            start_balance=start_balance,
            peak_equity=peak_equity,
        )

    async def calculate_lot(
        self,
        account_id: str,
        entry_price: float,
        stop_loss_price: float,
        direction: str,
        rr: Optional[float] = None,
        contract_size: Optional[float] = None,
        tick_value: Optional[float] = None,
        tick_size: Optional[float] = None,
        pip_value_per_lot: Optional[float] = None,
    ) -> LotCalculationResult:
        account = await self._load_account(account_id)
        profile = self._build_profile(account)
        return self.lot_calculator.calculate_lot(
            profile=profile,
            entry_price=entry_price,
            stop_loss_price=stop_loss_price,
            direction=direction,
            rr=rr,
            contract_size=contract_size,
            tick_value=tick_value,
            tick_size=tick_size,
            pip_value_per_lot=pip_value_per_lot,
        )

    async def check_profit_target(
        self,
        account_id: str,
        current_equity: float,
        start_balance: Optional[float] = None,
    ) -> ProfitTargetResult:
        """Enforce funded profit target. Blocks trading once the target is reached."""
        account = await self._load_account(account_id)
        profile = self._build_profile(account)

        if profile.account_type.upper() != "FUNDED":
            return ProfitTargetResult(
                allowed=True,
                reason="Account is not funded. Profit target not enforced.",
                profit_amount=0.0,
                profit_percent=0.0,
                profit_target_percent=(profile.profit_target or 0.0),
                start_balance=profile.balance,
                current_equity=current_equity,
            )

        if profile.profit_target is None:
            return ProfitTargetResult(
                allowed=True,
                reason="No profit target configured.",
                profit_amount=0.0,
                profit_percent=0.0,
                profit_target_percent=0.0,
                start_balance=profile.balance,
                current_equity=current_equity,
            )

        if start_balance is None:
            start_balance = profile.balance

        profit_amount = max(0.0, current_equity - start_balance)
        profit_percent = (
            profit_amount / start_balance * 100 if start_balance > 0 else 0.0
        )
        target_percent = profile.profit_target

        if profit_percent >= target_percent:
            return ProfitTargetResult(
                allowed=False,
                reason="Profit target reached",
                profit_amount=round(profit_amount, 2),
                profit_percent=round(profit_percent, 2),
                profit_target_percent=target_percent,
                start_balance=start_balance,
                current_equity=current_equity,
                warning="Evaluation passed. Trading stopped.",
            )

        return ProfitTargetResult(
            allowed=True,
            reason="Profit target not yet reached.",
            profit_amount=round(profit_amount, 2),
            profit_percent=round(profit_percent, 2),
            profit_target_percent=target_percent,
            start_balance=start_balance,
            current_equity=current_equity,
        )

    async def check_min_trading_days(self, account_id: str) -> MinTradingDaysResult:
        """Warn if the account has not met minimum trading days (funded eval). Not a block."""
        account = await self._load_account(account_id)
        profile = self._build_profile(account)

        if profile.account_type.upper() != "FUNDED":
            return MinTradingDaysResult(
                allowed=True,
                reason="Account is not funded. Minimum trading days not enforced.",
                min_trading_days=0,
                trading_days_count=0,
                days_remaining=0,
            )

        if profile.min_trading_days is None or profile.min_trading_days <= 0:
            return MinTradingDaysResult(
                allowed=True,
                reason="No minimum trading days configured.",
                min_trading_days=0,
                trading_days_count=profile.trading_days_count,
                days_remaining=0,
            )

        count = profile.trading_days_count
        required = profile.min_trading_days
        remaining = max(0, required - count)

        if count < required:
            return MinTradingDaysResult(
                allowed=True,
                reason="Minimum trading days not yet met.",
                min_trading_days=required,
                trading_days_count=count,
                days_remaining=remaining,
                warning=(
                    f"Minimum trading days: {required} required, "
                    f"{count} traded. {remaining} days remaining. "
                    "Prop firm may fail the account if not met."
                ),
            )

        return MinTradingDaysResult(
            allowed=True,
            reason="Minimum trading days met.",
            min_trading_days=required,
            trading_days_count=count,
            days_remaining=0,
        )

    async def record_trading_day(self, account_id: str) -> None:
        """Record today as a trading day for the account if not already recorded."""
        account = await self._load_account(account_id)
        risk: Optional[RiskProfile] = account.risk_profile
        if risk is None:
            return

        today = date.today().isoformat()

        dates: List[str] = []
        if risk.trading_dates:
            try:
                dates = json.loads(risk.trading_dates)
            except (ValueError, TypeError):
                dates = []

        if today not in dates:
            dates.append(today)
            risk.trading_dates = json.dumps(dates)
            risk.trading_days_count = len(dates)
            if risk.first_trade_date is None:
                risk.first_trade_date = datetime.now(timezone.utc)
            await self.session.flush()

    async def is_trade_allowed(self, account_id: str, current_equity: float,
                                daily_start_equity: float, planned_risk_amount: float = 0.0,
                                start_balance: Optional[float] = None) -> bool:
        account = await self._load_account(account_id)
        if not account.active:
            return False

        if account.account_type == "FUNDED":
            profit = await self.check_profit_target(account_id, current_equity, start_balance)
            if not profit.allowed:
                return False

        daily = await self.check_daily_loss(account_id, current_equity, daily_start_equity, planned_risk_amount)
        if not daily.allowed:
            return False

        maxl = await self.check_max_loss(account_id, current_equity, start_balance, planned_risk_amount)
        if not maxl.allowed:
            return False

        dd = await self.check_drawdown(account_id, current_equity, start_balance)
        if not dd.allowed:
            return False

        if account.account_type == "FUNDED":
            funded = await self.evaluate_funded_risk(account_id, current_equity, daily_start_equity, start_balance, planned_risk_amount)
            if not funded.allowed:
                return False

            min_days = await self.check_min_trading_days(account_id)
            if not min_days.allowed:
                return False

        return True

    async def detect_breaches(self, account_id: str, current_equity: float,
                               daily_start_equity: float) -> List[Dict[str, Any]]:
        breaches = []

        daily = await self.check_daily_loss(account_id, current_equity, daily_start_equity)
        if not daily.allowed:
            breaches.append({
                "type": "DAILY_LOSS",
                "state": daily.state,
                "reason": daily.reason,
                "daily_loss_percent": daily.projected_daily_loss_percent,
                "max_daily_loss_percent": daily.max_daily_loss_percent,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        maxl = await self.check_max_loss(account_id, current_equity)
        if not maxl.allowed:
            breaches.append({
                "type": "MAX_LOSS",
                "state": maxl.state,
                "reason": maxl.reason,
                "total_loss_percent": maxl.projected_total_loss_percent,
                "max_account_loss_percent": maxl.max_account_loss_percent,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        dd = await self.check_drawdown(account_id, current_equity)
        if not dd.allowed:
            breaches.append({
                "type": "DRAWDOWN",
                "state": dd.state,
                "reason": dd.reason,
                "drawdown_percent": max(dd.absolute_drawdown_percent, dd.floating_drawdown_percent),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        if account_id:
            account = await self._load_account(account_id)
            if account.account_type == "FUNDED":
                funded = await self.evaluate_funded_risk(account_id, current_equity, daily_start_equity)
                if not funded.allowed:
                    breaches.append({
                        "type": "FUNDED_RULE",
                        "state": funded.risk_state,
                        "reason": funded.reason,
                        "daily_loss_percent": funded.daily_loss_percent,
                        "total_loss_percent": funded.total_loss_percent,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

        return breaches

import logging
from datetime import date, datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from database.models import TradingAccount, RiskProfile
from database.repositories import AccountRepository, UserRepository, LicenseRepository

logger = logging.getLogger(__name__)


class AccountNotFoundError(Exception):
    pass


class AccountNotVerifiedError(Exception):
    pass


class AccountNotActiveError(Exception):
    pass


class AccountManager:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.acc_repo = AccountRepository(session)
        self.user_repo = UserRepository(session)
        self.lic_repo = LicenseRepository(session)

    async def get_account(self, account_id: str) -> Optional[TradingAccount]:
        return await self.acc_repo.get_by_id(account_id)

    async def get_active_accounts(self, user_id: Optional[str] = None) -> List[TradingAccount]:
        if user_id:
            return await self.acc_repo.get_active_by_user_id(user_id)
        stmt = __import__("sqlalchemy").select(TradingAccount).where(TradingAccount.active == True)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_all_accounts(self, user_id: Optional[str] = None) -> List[TradingAccount]:
        if user_id:
            return await self.acc_repo.get_by_user_id(user_id)
        stmt = __import__("sqlalchemy").select(TradingAccount)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def activate_account(self, account_id: str) -> TradingAccount:
        account = await self.acc_repo.get_by_id(account_id)
        if not account:
            raise AccountNotFoundError(f"Account {account_id} not found")
        if not account.verified:
            raise AccountNotVerifiedError("Account is not verified")
        if not account.license_id:
            raise AccountNotVerifiedError("No license bound to this account")
        account.active = True
        account.engine_status = "ACTIVE"
        await self.session.flush()
        return account

    async def pause_account(self, account_id: str) -> TradingAccount:
        account = await self.acc_repo.get_by_id(account_id)
        if not account:
            raise AccountNotFoundError(f"Account {account_id} not found")
        account.active = False
        account.engine_status = "PAUSED"
        await self.session.flush()
        return account

    async def resume_account(self, account_id: str) -> TradingAccount:
        account = await self.acc_repo.get_by_id(account_id)
        if not account:
            raise AccountNotFoundError(f"Account {account_id} not found")
        if not account.verified:
            raise AccountNotVerifiedError("Account is not verified")
        account.active = True
        account.engine_status = "ACTIVE"
        await self.session.flush()
        return account

    async def disable_account(self, account_id: str, reason: Optional[str] = None) -> TradingAccount:
        account = await self.acc_repo.get_by_id(account_id)
        if not account:
            raise AccountNotFoundError(f"Account {account_id} not found")
        account.active = False
        account.engine_status = "DISABLED"
        await self.session.flush()
        return account

    async def update_balance(self, account_id: str, balance: float) -> TradingAccount:
        account = await self.acc_repo.get_by_id(account_id)
        if not account:
            raise AccountNotFoundError(f"Account {account_id} not found")
        account.balance_snapshot = balance
        await self.session.flush()
        return account

    async def update_equity(self, account_id: str, equity: float) -> TradingAccount:
        account = await self.acc_repo.get_by_id(account_id)
        if not account:
            raise AccountNotFoundError(f"Account {account_id} not found")
        account.equity_snapshot = equity
        await self.session.flush()
        return account

    async def update_drawdown(self, account_id: str, balance: float, equity: float) -> Dict[str, Optional[float]]:
        account = await self.acc_repo.get_by_id(account_id)
        if not account:
            raise AccountNotFoundError(f"Account {account_id} not found")

        account.balance_snapshot = balance
        account.equity_snapshot = equity

        risk = account.risk_profile
        if risk is None:
            risk = RiskProfile(account_id=account_id)
            self.session.add(risk)
            await self.session.flush()

        now = datetime.now(timezone.utc)
        today = now.date()

        # --- initial_balance: set once on first scan, use account_size if available ---
        if risk.initial_balance is None or risk.initial_balance <= 0:
            risk.initial_balance = account.account_size or balance

        # --- detect new trading day ---
        last_update = risk.last_risk_update
        if last_update is None or last_update.date() != today:
            risk.day_start_balance = balance
            # use balance as day_start_equity on first init so existing losses are captured
            risk.day_start_equity = balance if last_update is None else equity
            risk.daily_high_equity = risk.day_start_equity

        # --- update daily high (for trailing drawdown reference) ---
        current_high = risk.daily_high_equity or equity
        risk.daily_high_equity = max(current_high, equity)

        # --- compute current daily loss ---
        day_start = risk.day_start_equity or equity
        daily_loss_amount = max(0.0, day_start - equity)
        risk.current_daily_loss_pct = round(
            (daily_loss_amount / day_start * 100) if day_start > 0 else 0.0, 2
        )

        # --- compute current max loss ---
        if risk.drawdown_type == "trailing":
            reference = max(risk.initial_balance, risk.daily_high_equity)
        else:
            reference = risk.initial_balance or balance

        max_loss_amount = max(0.0, reference - equity)
        risk.current_max_loss_pct = round(
            (max_loss_amount / reference * 100) if reference > 0 else 0.0, 2
        )

        risk.last_risk_update = now
        await self.session.flush()

        return {
            "initial_balance": risk.initial_balance,
            "day_start_equity": risk.day_start_equity,
            "current_daily_loss_pct": risk.current_daily_loss_pct,
            "current_max_loss_pct": risk.current_max_loss_pct,
        }

    async def update_engine_status(self, account_id: str, status: str) -> TradingAccount:
        account = await self.acc_repo.get_by_id(account_id)
        if not account:
            raise AccountNotFoundError(f"Account {account_id} not found")
        account.engine_status = status
        await self.session.flush()
        return account

    async def set_license(self, account_id: str, license_id: str) -> TradingAccount:
        account = await self.acc_repo.get_by_id(account_id)
        if not account:
            raise AccountNotFoundError(f"Account {account_id} not found")
        account.license_id = license_id
        await self.session.flush()
        return account

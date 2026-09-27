from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import TradingAccount, RiskProfile
from security.encryption import encrypt
from security.account_fingerprint import build_account_fingerprint


class AccountAlreadyLinkedToUserError(Exception):
    """Same user trying to re-add an already bound account."""
    pass


class AccountLinkedToAnotherUserError(Exception):
    """Different user trying to bind an already bound account."""
    pass


class AccountNotFoundError(Exception):
    """Account not found or doesn't belong to user."""
    pass


def _to_float(val) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().upper().replace(" ", "").replace(",", "")
    try:
        if s.endswith("K"):
            return float(s[:-1]) * 1000
        if s.endswith("M"):
            return float(s[:-1]) * 1000000
        return float(s)
    except (ValueError, TypeError):
        return None


class AccountRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, account_id: str) -> Optional[TradingAccount]:
        return await self.session.get(TradingAccount, account_id)

    async def get_by_user_id(self, user_id: str) -> List[TradingAccount]:
        stmt = select(TradingAccount).where(TradingAccount.user_id == user_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_awaiting_activation(self, user_id: str) -> List[TradingAccount]:
        stmt = (
            select(TradingAccount)
            .where(TradingAccount.user_id == user_id)
            .where(TradingAccount.verified == True)
            .where(TradingAccount.active == False)
            .order_by(TradingAccount.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_active_by_user_id(self, user_id: str) -> List[TradingAccount]:
        stmt = (
            select(TradingAccount)
            .where(TradingAccount.user_id == user_id)
            .where(TradingAccount.active == True)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_bound_by_fingerprint(self, fingerprint: str) -> Optional[TradingAccount]:
        stmt = select(TradingAccount).where(
            TradingAccount.account_fingerprint == fingerprint,
            TradingAccount.removed_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_from_wizard(
        self,
        user_id: str,
        setup_data: dict,
        encrypted_password: Optional[str] = None,
        account_fingerprint: Optional[str] = None,
    ) -> TradingAccount:
        account_type = (setup_data.get("account", {}) or {}).get("type", "PERSONAL")
        prop_firm_data = (setup_data.get("prop_firm", {}) or {})
        broker_data = (setup_data.get("broker", {}) or {})
        platform_data = (setup_data.get("platform", {}) or {})
        scan_data = setup_data.get("scan", {}) or {}

        # encrypt password before storing
        pw_to_store = encrypted_password
        if pw_to_store:
            pw_to_store = encrypt(pw_to_store)

        account = TradingAccount(
            user_id=user_id,
            account_type=account_type.upper() if account_type else "PERSONAL",
            broker=broker_data.get("name"),
            prop_firm=prop_firm_data.get("name"),
            program=prop_firm_data.get("program_name"),
            program_type=prop_firm_data.get("account_type"),
            platform=platform_data.get("platform", "MT5"),
            server=platform_data.get("server"),
            login=platform_data.get("login"),
            encrypted_password=pw_to_store,
            account_size=_to_float(platform_data.get("balance")) or _to_float(prop_firm_data.get("account_size")) or _to_float(scan_data.get("balance_detected")),
            demo_real=platform_data.get("demo_real") or scan_data.get("demo_real"),
            trade_mode=setup_data.get("account", {}).get("trade_mode"),
            currency=setup_data.get("account", {}).get("currency", "USD"),
            leverage=platform_data.get("leverage") or scan_data.get("leverage_detected"),
            balance_snapshot=_to_float(scan_data.get("balance_detected")),
            equity_snapshot=_to_float(scan_data.get("equity_detected")),
            symbol_mapping=scan_data.get("symbol_mapping"),
            account_fingerprint=account_fingerprint or build_account_fingerprint(
                platform=platform_data.get("platform", "MT5"),
                server=platform_data.get("server"),
                login=platform_data.get("login"),
            ),
        )
        self.session.add(account)
        await self.session.flush()

        # create risk profile
        risk_data = setup_data.get("risk", {}) or prop_firm_data.get("risk", {}) or {}
        risk = RiskProfile(
            account_id=account.id,
            daily_loss=risk_data.get("daily_loss"),
            max_loss=risk_data.get("max_loss"),
            profit_target=risk_data.get("profit_target"),
            mode=risk_data.get("mode", "balanced"),
            min_trading_days=risk_data.get("min_trading_days") or risk_data.get("min_trades"),
        )
        self.session.add(risk)
        await self.session.flush()

        return account

    async def create_client_account(
        self,
        account: TradingAccount,
        risk_profile: RiskProfile,
    ) -> TradingAccount:
        """Persist a web account and its risk aggregate atomically in-session."""
        self.session.add(account)
        await self.session.flush()
        risk_profile.account_id = account.id
        self.session.add(risk_profile)
        await self.session.flush()
        return account

    async def verify(self, account_id: str) -> Optional[TradingAccount]:
        account = await self.get_by_id(account_id)
        if account:
            account.verified = True
        return account

    async def activate(self, account_id: str) -> Optional[TradingAccount]:
        account = await self.get_by_id(account_id)
        if account:
            account.active = True
            account.verified = True
        return account

    async def deactivate(self, account_id: str) -> Optional[TradingAccount]:
        account = await self.get_by_id(account_id)
        if account:
            account.active = False
        return account

    async def hard_delete(self, account_id: str) -> None:
        from database.models import RiskProfile, AccountScan, PaperTrade, AuditLog

        await self.session.execute(
            RiskProfile.__table__.delete().where(RiskProfile.account_id == account_id)
        )
        await self.session.execute(
            AccountScan.__table__.delete().where(AccountScan.account_id == account_id)
        )
        await self.session.execute(
            PaperTrade.__table__.delete().where(PaperTrade.account_id == account_id)
        )
        await self.session.execute(
            AuditLog.__table__.delete().where(AuditLog.account_id == account_id)
        )

        account = await self.get_by_id(account_id)
        if account:
            await self.session.delete(account)
        await self.session.flush()

    async def remove_account(self, account_id: str, user_id: str) -> TradingAccount:
        from sqlalchemy.exc import IntegrityError

        account = await self.get_by_id(account_id)
        if not account or account.user_id != user_id:
            raise AccountNotFoundError()

        account.active = False
        account.verified = False
        account.engine_status = "REMOVED"
        account.real_trading_enabled = False
        account.license_id = None
        account.encrypted_password = None
        account.removed_at = datetime.now(timezone.utc)

        try:
            await self.session.flush()
        except IntegrityError:
            await self.session.rollback()
            raise

        return account

    async def update_snapshot(
        self,
        account_id: str,
        balance: float,
        equity: float,
    ) -> Optional[TradingAccount]:
        account = await self.get_by_id(account_id)
        if account:
            account.balance_snapshot = balance
            account.equity_snapshot = equity
        return account

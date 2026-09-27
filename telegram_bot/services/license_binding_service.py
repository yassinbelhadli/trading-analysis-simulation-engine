from typing import Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from database.models import License, TradingAccount
from database.repositories import LicenseRepository, AccountRepository


class LicenseBindingError(Exception):
    pass


class LicenseBindingService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.license_repo = LicenseRepository(session)
        self.account_repo = AccountRepository(session)

    async def bind_license_to_account(
        self,
        license_key: str,
        account: TradingAccount,
        telegram_id: int = None,
    ) -> Tuple[License, TradingAccount]:
        lic = await self.license_repo.get_by_key(license_key)
        if not lic:
            raise LicenseBindingError("License key not found")

        if lic.status != "active":
            raise LicenseBindingError("License is not active")

        if lic.expires_at and lic.expires_at.replace(tzinfo=None) < __import__("datetime").datetime.now(__import__("datetime").timezone.utc).replace(tzinfo=None):
            raise LicenseBindingError("License has expired")

        if lic.user_id != account.user_id:
            raise LicenseBindingError("License does not belong to this user")

        if lic.telegram_id is not None and telegram_id is not None and lic.telegram_id != telegram_id:
            raise LicenseBindingError("License is bound to another Telegram account")

        active_count = await self._count_active_accounts(lic.id)
        if active_count >= lic.max_accounts:
            raise LicenseBindingError(f"Max accounts ({lic.max_accounts}) reached for this license")

        account.license_id = lic.id
        account.engine_status = "WAITING_ACTIVATION"
        await self.session.flush()

        return lic, account

    async def _count_active_accounts(self, license_id: str) -> int:
        from sqlalchemy import select, func
        stmt = (
            select(func.count())
            .select_from(TradingAccount)
            .where(TradingAccount.license_id == license_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def find_available_license(self, user_id: str) -> Optional[License]:
        licenses = await self.license_repo.get_by_user_id(user_id)
        for lic in licenses:
            if lic.status != "active":
                continue
            if lic.expires_at and lic.expires_at.replace(tzinfo=None) < __import__("datetime").datetime.now(__import__("datetime").timezone.utc).replace(tzinfo=None):
                continue
            active_count = await self._count_active_accounts(lic.id)
            if active_count < lic.max_accounts:
                return lic
        return None

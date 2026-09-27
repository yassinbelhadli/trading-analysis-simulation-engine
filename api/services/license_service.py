"""Application service for client-facing license workflows."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from database.models import License, TradingAccount
from database.repositories import AccountRepository, LicenseRepository
from security.audit import log_event


UNLIMITED_PLANS = {"infinity", "enterprise", "unlimited"}


class LicenseServiceError(Exception):
    """Base error for client license workflows."""


class LicenseInputError(LicenseServiceError):
    """The request is missing required license data."""


class LicenseNotFoundError(LicenseServiceError):
    """The requested license does not exist."""


class LicenseOwnershipError(LicenseServiceError):
    """The license belongs to another user."""


class LicenseInactiveError(LicenseServiceError):
    """The license is not active."""


class LicenseExpiredError(LicenseServiceError):
    """The license has expired."""


class LicenseAlreadyBoundError(LicenseServiceError):
    """The license is already bound to an account."""


class LicenseAccountNotFoundError(LicenseServiceError):
    """The requested account does not exist for the current user."""


class LicenseService:
    """Coordinate license lookup and client binding workflows."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.license_repository = LicenseRepository(session)
        self.account_repository = AccountRepository(session)

    async def list_user_licenses(self, user_id: str) -> List[License]:
        """Return the user's licenses in the existing newest-first order."""
        licenses = await self.license_repository.get_by_user_id_ordered(user_id)
        return licenses

    async def get_active_license(self, user_id: str) -> Optional[License]:
        """Return the newest active, non-expired license for a user."""
        now = datetime.now(timezone.utc)
        for license_row in await self.list_user_licenses(user_id):
            if license_row.status == "active" and (
                license_row.expires_at is None or license_row.expires_at >= now
            ):
                return license_row
        return None

    async def get_account_limits(
        self,
        user_id: str,
        license_id: Optional[str] = None,
    ) -> dict:
        """Return account usage limits using the existing client semantics."""
        accounts = await self.account_repository.get_by_user_id(user_id)
        used = sum(1 for account in accounts if account.removed_at is None)
        license_row = (
            await self.license_repository.get_by_id(license_id)
            if license_id
            else await self.get_active_license(user_id)
        )
        max_accounts = license_row.max_accounts if license_row else 0
        unlimited = bool(
            license_row
            and (
                (license_row.plan or "").lower() in UNLIMITED_PLANS
                or max_accounts >= 999
            )
        )
        return {"used": used, "max": max_accounts, "unlimited": unlimited}

    async def bind_license(
        self,
        user_id: str,
        license_key: str,
        account_id: str,
    ) -> Tuple[License, TradingAccount]:
        """Bind an owned active license to an owned account and audit it."""
        license_key = license_key.strip().upper()
        account_id = account_id.strip()
        if not license_key or not account_id:
            raise LicenseInputError("license_key and account_id are required")

        license_row = await self.license_repository.get_by_key(license_key)
        if not license_row:
            raise LicenseNotFoundError("License not found")
        if license_row.user_id != user_id:
            raise LicenseOwnershipError("License does not belong to you")
        if license_row.status != "active":
            raise LicenseInactiveError("License is not active")
        if license_row.expires_at and license_row.expires_at < datetime.now(timezone.utc):
            raise LicenseExpiredError("License has expired")
        if license_row.bound_account_id:
            raise LicenseAlreadyBoundError("License already bound to an account. Unbind first.")

        account = await self.account_repository.get_by_id(account_id)
        if not account or account.user_id != user_id:
            raise LicenseAccountNotFoundError("Account not found")

        license_row.bound_account_id = account.id
        license_row.bound_at = datetime.now(timezone.utc)
        license_row.transfer_locked = True
        account.license_id = license_row.id
        account.engine_status = "ACTIVE"

        await log_event(
            self.session,
            "license.bound",
            f"License {license_key} bound to account {account_id}",
            user_id=user_id,
        )
        await self.session.commit()
        return license_row, account

    async def unbind_license(self, user_id: str, license_key: str) -> License:
        """Unbind an owned license and restore the account activation state."""
        license_key = license_key.strip().upper()
        if not license_key:
            raise LicenseInputError("license_key is required")

        license_row = await self.license_repository.get_by_key(license_key)
        if not license_row:
            raise LicenseNotFoundError("License not found")
        if license_row.user_id != user_id:
            raise LicenseOwnershipError("License does not belong to you")

        if license_row.bound_account_id:
            account = await self.account_repository.get_by_id(license_row.bound_account_id)
            if account:
                account.license_id = None
                account.engine_status = "WAITING_ACTIVATION"

        license_row.bound_account_id = None
        license_row.bound_at = None
        license_row.telegram_id = None
        license_row.transfer_locked = False

        await log_event(
            self.session,
            "license.unbound",
            f"License {license_key} unbound by user",
            user_id=user_id,
        )
        await self.session.commit()
        return license_row

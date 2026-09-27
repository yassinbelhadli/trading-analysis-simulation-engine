from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import License


@dataclass
class LicenseResult:
    valid: bool
    state: str
    message: str
    plan: Optional[str] = None
    expiry: Optional[str] = None
    license_obj: Optional[License] = None


class LicenseService:
    async def check(
        self,
        session: AsyncSession,
        user_id: str,
        telegram_id: int = None,
    ) -> LicenseResult:
        stmt = (
            select(License)
            .where(License.user_id == user_id)
            .where(License.status == "active")
            .limit(1)
        )
        result = await session.execute(stmt)
        lic = result.scalar_one_or_none()

        if not lic:
            return LicenseResult(
                valid=False,
                state="NO_LICENSE",
                message="No active license found.",
            )

        if lic.telegram_id is not None and telegram_id is not None and lic.telegram_id != telegram_id:
            return LicenseResult(
                valid=False,
                state="BOUND_TO_OTHER",
                message="License is bound to another Telegram account.",
            )

        return LicenseResult(
            valid=True,
            state="ACTIVE",
            message="License is active.",
            plan=lic.plan,
            expiry=str(lic.expires_at) if lic.expires_at else None,
            license_obj=lic,
        )


license_service = LicenseService()

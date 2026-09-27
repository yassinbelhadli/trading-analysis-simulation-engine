from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import License


class LicenseRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, license_id: str) -> Optional[License]:
        return await self.session.get(License, license_id)

    async def get_by_key(self, license_key: str) -> Optional[License]:
        stmt = select(License).where(License.license_key == license_key)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_user_id(self, user_id: str) -> List[License]:
        stmt = select(License).where(License.user_id == user_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_user_id_ordered(self, user_id: str) -> List[License]:
        """Return a user's licenses in newest-first creation order."""
        stmt = (
            select(License)
            .where(License.user_id == user_id)
            .order_by(License.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        user_id: str,
        license_key: str,
        plan: str = "standard",
        max_accounts: int = 1,
        expires_at: Optional[datetime] = None,
    ) -> License:
        lic = License(
            user_id=user_id,
            license_key=license_key,
            plan=plan,
            max_accounts=max_accounts,
            expires_at=expires_at,
        )
        self.session.add(lic)
        await self.session.flush()
        return lic

    async def activate(self, license_id: str) -> Optional[License]:
        lic = await self.get_by_id(license_id)
        if lic:
            lic.status = "active"
        return lic

    async def deactivate(self, license_id: str) -> Optional[License]:
        lic = await self.get_by_id(license_id)
        if lic:
            lic.status = "inactive"
        return lic

    async def delete(self, license_id: str) -> bool:
        lic = await self.get_by_id(license_id)
        if not lic:
            return False
        await self.session.delete(lic)
        return True

    async def is_valid(self, license_key: str) -> bool:
        lic = await self.get_by_key(license_key)
        if not lic:
            return False
        if lic.status != "active":
            return False
        if lic.expires_at and lic.expires_at < datetime.now(timezone.utc):
            return False
        return True

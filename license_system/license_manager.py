from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import License
from security.license_gen import generate_license_key

logger = logging.getLogger(__name__)


async def create_license(
    session: AsyncSession,
    user_id: str,
    plan: str = "starter",
    max_accounts: int = 1,
    expires_in_days: Optional[int] = None,
    created_by: Optional[str] = None,
) -> License:
    from datetime import timedelta
    key = generate_license_key()
    expires_at = None
    if expires_in_days:
        expires_at = datetime.now(timezone.utc).replace(hour=23, minute=59, second=59) + timedelta(days=expires_in_days)

    lic = License(
        user_id=user_id,
        license_key=key,
        plan=plan,
        max_accounts=max_accounts,
        expires_at=expires_at,
        status="active",
    )
    session.add(lic)
    await session.flush()
    logger.info("License %s created for user %s (plan=%s, by=%s)", key, user_id, plan, created_by or "system")
    return lic


async def check_expired_licenses(session: AsyncSession) -> list[License]:
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(License).where(
            License.status == "active",
            License.expires_at.isnot(None),
            License.expires_at < now,
        )
    )
    expired = list(result.scalars().all())
    for lic in expired:
        lic.status = "expired"
        logger.info("License %s expired", lic.license_key)
    if expired:
        await session.commit()
    return expired


async def get_license_by_key(session: AsyncSession, key: str) -> Optional[License]:
    result = await session.execute(select(License).where(License.license_key == key.upper()))
    return result.scalar_one_or_none()


async def get_user_licenses(session: AsyncSession, user_id: str) -> list[License]:
    result = await session.execute(
        select(License).where(License.user_id == user_id).order_by(License.created_at.desc())
    )
    return list(result.scalars().all())

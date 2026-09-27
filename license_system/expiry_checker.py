from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import License, TradingAccount

logger = logging.getLogger(__name__)


async def check_expiring_licenses(session: AsyncSession, days_before: int = 7) -> list[License]:
    now = datetime.now(timezone.utc)
    threshold = now.replace(hour=23, minute=59, second=59) + timedelta(days=days_before)
    result = await session.execute(
        select(License).where(
            License.status == "active",
            License.expires_at.isnot(None),
            License.expires_at.between(now, threshold),
        )
    )
    return list(result.scalars().all())


async def expire_license(session: AsyncSession, license_id: str) -> License:
    result = await session.execute(select(License).where(License.id == license_id))
    lic = result.scalar_one_or_none()
    if not lic:
        raise ValueError("License not found")
    lic.status = "expired"
    if lic.bound_account_id:
        acc_result = await session.execute(select(TradingAccount).where(TradingAccount.id == lic.bound_account_id))
        account = acc_result.scalar_one_or_none()
        if account:
            account.engine_status = "DISABLED"
    await session.commit()
    logger.info("License %s expired", lic.license_key)
    return lic


async def renew_license(
    session: AsyncSession,
    license_id: str,
    additional_days: int = 30,
) -> License:
    result = await session.execute(select(License).where(License.id == license_id))
    lic = result.scalar_one_or_none()
    if not lic:
        raise ValueError("License not found")
    now = datetime.now(timezone.utc)
    if lic.expires_at and lic.expires_at > now:
        lic.expires_at = lic.expires_at.replace(hour=23, minute=59, second=59) + timedelta(days=additional_days)
    else:
        lic.expires_at = now.replace(hour=23, minute=59, second=59) + timedelta(days=additional_days)
    lic.status = "active"
    await session.commit()
    logger.info("License %s renewed (+%d days)", lic.license_key, additional_days)
    return lic

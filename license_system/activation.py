from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import License, TradingAccount

logger = logging.getLogger(__name__)


async def activate_license(
    session: AsyncSession,
    license_id: str,
    account_id: Optional[str] = None,
) -> License:
    result = await session.execute(select(License).where(License.id == license_id))
    lic = result.scalar_one_or_none()
    if not lic:
        raise ValueError("License not found")
    if lic.expires_at and lic.expires_at < datetime.now(timezone.utc):
        raise ValueError("License has expired")
    if lic.status == "suspended":
        raise ValueError("License is suspended")

    lic.status = "active"
    if account_id:
        lic.bound_account_id = account_id
        lic.bound_at = datetime.now(timezone.utc)
        acc_result = await session.execute(select(TradingAccount).where(TradingAccount.id == account_id))
        account = acc_result.scalar_one_or_none()
        if account:
            account.license_id = lic.id
            account.engine_status = "ACTIVE"

    await session.commit()
    logger.info("License %s activated (account=%s)", lic.license_key, account_id)
    return lic


async def deactivate_license(session: AsyncSession, license_id: str) -> License:
    result = await session.execute(select(License).where(License.id == license_id))
    lic = result.scalar_one_or_none()
    if not lic:
        raise ValueError("License not found")
    lic.status = "inactive"
    await session.commit()
    logger.info("License %s deactivated", lic.license_key)
    return lic


async def suspend_license(session: AsyncSession, license_id: str, reason: str = "") -> License:
    result = await session.execute(select(License).where(License.id == license_id))
    lic = result.scalar_one_or_none()
    if not lic:
        raise ValueError("License not found")

    lic.status = "suspended"
    if lic.bound_account_id:
        acc_result = await session.execute(select(TradingAccount).where(TradingAccount.id == lic.bound_account_id))
        account = acc_result.scalar_one_or_none()
        if account:
            account.engine_status = "SUSPENDED"

    await session.commit()
    logger.info("License %s suspended (reason=%s)", lic.license_key, reason)
    return lic

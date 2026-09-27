from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import AccountScan


class ScanRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, scan_id: str) -> Optional[AccountScan]:
        return await self.session.get(AccountScan, scan_id)

    async def get_by_account_id(self, account_id: str) -> List[AccountScan]:
        stmt = (
            select(AccountScan)
            .where(AccountScan.account_id == account_id)
            .order_by(AccountScan.scanned_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_by_account(self, account_id: str) -> Optional[AccountScan]:
        stmt = (
            select(AccountScan)
            .where(AccountScan.account_id == account_id)
            .order_by(AccountScan.scanned_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        account_id: str,
        broker_detected: Optional[str] = None,
        balance_detected: Optional[float] = None,
        equity_detected: Optional[float] = None,
        leverage_detected: Optional[str] = None,
        symbols_detected: Optional[str] = None,
        mismatches: Optional[str] = None,
        build: Optional[int] = None,
        timezone_detected: Optional[str] = None,
        scan_status: str = "pending",
    ) -> AccountScan:
        scan = AccountScan(
            account_id=account_id,
            broker_detected=broker_detected,
            balance_detected=balance_detected,
            equity_detected=equity_detected,
            leverage_detected=leverage_detected,
            symbols_detected=symbols_detected,
            mismatches=mismatches,
            build=build,
            timezone_detected=timezone_detected,
            scan_status=scan_status,
        )
        self.session.add(scan)
        await self.session.flush()
        return scan

    async def update_status(self, scan_id: str, status: str) -> Optional[AccountScan]:
        scan = await self.get_by_id(scan_id)
        if scan:
            scan.scan_status = status
        return scan

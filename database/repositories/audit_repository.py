from datetime import datetime, timezone, timedelta
from typing import Optional, List

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import AuditLog


class AuditRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, log: AuditLog) -> AuditLog:
        self.session.add(log)
        await self.session.flush()
        return log

    async def get_by_id(self, log_id: str) -> Optional[AuditLog]:
        return await self.session.get(AuditLog, log_id)

    async def get_by_account(
        self, account_id: str, limit: int = 100, offset: int = 0
    ) -> List[AuditLog]:
        stmt = (
            select(AuditLog)
            .where(AuditLog.account_id == account_id)
            .order_by(desc(AuditLog.created_at))
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_user(
        self, user_id: str, limit: int = 100, offset: int = 0
    ) -> List[AuditLog]:
        stmt = (
            select(AuditLog)
            .where(AuditLog.user_id == user_id)
            .order_by(desc(AuditLog.created_at))
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_event_type(
        self, event_type: str, limit: int = 100, offset: int = 0
    ) -> List[AuditLog]:
        stmt = (
            select(AuditLog)
            .where(AuditLog.event_type == event_type)
            .order_by(desc(AuditLog.created_at))
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_recent(
        self, limit: int = 100, severity: Optional[str] = None
    ) -> List[AuditLog]:
        stmt = select(AuditLog)
        if severity:
            stmt = stmt.where(AuditLog.severity == severity)
        stmt = stmt.order_by(desc(AuditLog.created_at)).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_time_range(
        self, since: datetime, until: Optional[datetime] = None,
        limit: int = 1000,
    ) -> List[AuditLog]:
        stmt = select(AuditLog).where(AuditLog.created_at >= since)
        if until:
            stmt = stmt.where(AuditLog.created_at <= until)
        stmt = stmt.order_by(desc(AuditLog.created_at)).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_severity(self, since: Optional[datetime] = None) -> dict:
        from sqlalchemy import func
        stmt = select(AuditLog.severity, func.count(AuditLog.id))
        if since:
            stmt = stmt.where(AuditLog.created_at >= since)
        stmt = stmt.group_by(AuditLog.severity)
        result = await self.session.execute(stmt)
        return {row[0]: row[1] for row in result}

    async def delete_older_than(self, days: int) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        stmt = select(AuditLog).where(AuditLog.created_at < cutoff)
        result = await self.session.execute(stmt)
        logs = list(result.scalars().all())
        for log in logs:
            await self.session.delete(log)
        await self.session.flush()
        return len(logs)

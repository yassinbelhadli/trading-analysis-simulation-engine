"""User-scoped read queries for persisted paper trades."""
from __future__ import annotations

from typing import List

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import PaperTrade


class TradeRepository:
    """Read-only paper-trade queries shared by dashboard consumers."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_closed_for_user(
        self,
        user_id: str,
        *,
        descending: bool = False,
        limit: int | None = None,
    ) -> List[PaperTrade]:
        """Return closed trades for a user in the requested close-time order."""
        order = desc(PaperTrade.closed_at) if descending else PaperTrade.closed_at
        stmt = (
            select(PaperTrade)
            .where(PaperTrade.user_id == user_id, PaperTrade.status == "CLOSED")
            .order_by(order)
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_open_for_user(self, user_id: str) -> List[PaperTrade]:
        """Return planned or filled trades for a user."""
        stmt = select(PaperTrade).where(
            PaperTrade.user_id == user_id,
            PaperTrade.status.in_(["PLANNED", "FILLED"]),
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_planned_for_user(self, user_id: str, limit: int) -> List[PaperTrade]:
        """Return the newest planned trades for a user."""
        stmt = (
            select(PaperTrade)
            .where(PaperTrade.user_id == user_id, PaperTrade.status == "PLANNED")
            .order_by(desc(PaperTrade.created_at))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

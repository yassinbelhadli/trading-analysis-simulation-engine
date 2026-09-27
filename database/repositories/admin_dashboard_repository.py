"""Aggregate read queries used by the admin dashboard overview."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import AuditLog, PaperTrade, Subscription, TradingAccount, User


@dataclass(frozen=True)
class AdminOverviewCounts:
    """Database counts required by the existing admin overview contract."""

    active_trades: int
    total_clients: int
    active_subscriptions: int
    connected_accounts: int
    errors_24h: int


class AdminDashboardQueryRepository:
    """Read-only aggregate queries for admin dashboard views."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_overview_counts(self) -> AdminOverviewCounts:
        """Return the existing overview counts without changing their semantics."""
        result = await self.session.execute(
            select(func.count()).select_from(PaperTrade).where(PaperTrade.status.in_(["OPEN", "ACTIVE"]))
        )
        active_trades = result.scalar() or 0

        result = await self.session.execute(select(func.count()).select_from(User))
        total_clients = result.scalar() or 0

        result = await self.session.execute(
            select(func.count()).select_from(Subscription).where(Subscription.active == True)
        )
        active_subscriptions = result.scalar() or 0

        result = await self.session.execute(
            select(func.count()).select_from(TradingAccount).where(TradingAccount.active == True)
        )
        connected_accounts = result.scalar() or 0

        since = datetime.now(timezone.utc) - timedelta(hours=24)
        result = await self.session.execute(
            select(func.count()).select_from(AuditLog).where(
                AuditLog.created_at >= since,
                AuditLog.severity.in_(["ERROR", "CRITICAL"]),
            )
        )
        errors_24h = result.scalar() or 0

        return AdminOverviewCounts(
            active_trades=active_trades,
            total_clients=total_clients,
            active_subscriptions=active_subscriptions,
            connected_accounts=connected_accounts,
            errors_24h=errors_24h,
        )

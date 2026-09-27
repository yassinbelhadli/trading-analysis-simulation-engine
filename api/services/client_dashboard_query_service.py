"""Read-only orchestration for the existing client dashboard contract."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from database.models import License, PaperTrade, TradingAccount, User
from database.repositories import AccountRepository, LicenseRepository, TradeRepository


@dataclass(frozen=True)
class ClientDashboardRead:
    """Database-backed inputs consumed by the pure dashboard aggregator."""

    user: User
    licenses: list[License]
    accounts: list[TradingAccount]
    closed_trades: list[PaperTrade]
    open_trades: list[PaperTrade]
    recent_signals: list[PaperTrade]
    recent_trades: list[PaperTrade]


class ClientDashboardQueryService:
    """Compose owner-scoped repository reads without calculations or writes."""

    def __init__(self, session: AsyncSession):
        self.license_repository = LicenseRepository(session)
        self.account_repository = AccountRepository(session)
        self.trade_repository = TradeRepository(session)

    async def load_dashboard(self, user: User) -> ClientDashboardRead:
        """Load all source rows required by the existing client home response."""
        return ClientDashboardRead(
            user=user,
            licenses=await self.license_repository.get_by_user_id_ordered(user.id),
            accounts=await self.account_repository.get_active_by_user_id(user.id),
            closed_trades=await self.trade_repository.list_closed_for_user(user.id),
            open_trades=await self.trade_repository.list_open_for_user(user.id),
            recent_signals=await self.trade_repository.list_planned_for_user(user.id, 5),
            recent_trades=await self.trade_repository.list_closed_for_user(
                user.id,
                descending=True,
                limit=5,
            ),
        )

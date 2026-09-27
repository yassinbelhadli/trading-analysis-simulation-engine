"""Read-only orchestration for the existing admin overview contract."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from api.services.admin_health_service import admin_health_service
from database.repositories.admin_dashboard_repository import (
    AdminDashboardQueryRepository,
    AdminOverviewCounts,
)


@dataclass(frozen=True)
class AdminDashboardRead:
    """Repository and health inputs consumed by the admin aggregator."""

    engine: dict
    counts: AdminOverviewCounts


class AdminDashboardQueryService:
    """Compose repository and health reads without writes or business rules."""

    def __init__(self, session: AsyncSession):
        self.repository = AdminDashboardQueryRepository(session)

    async def load_overview(self) -> AdminDashboardRead:
        """Load the source data required by the existing admin overview."""
        counts = await self.repository.get_overview_counts()
        return AdminDashboardRead(
            engine=admin_health_service.get_overview_engine(),
            counts=counts,
        )

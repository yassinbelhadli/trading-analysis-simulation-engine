from __future__ import annotations

import logging
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.admin_dashboard_aggregator import AdminDashboardAggregator
from api.services.admin_dashboard_query_service import AdminDashboardQueryService

logger = logging.getLogger(__name__)


async def get_overview(session: AsyncSession) -> dict:
    read = await AdminDashboardQueryService(session).load_overview()
    return AdminDashboardAggregator().build(read).model_dump()

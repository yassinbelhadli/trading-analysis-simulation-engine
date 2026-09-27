from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.admin import OverviewResponse
from api.services.admin_dashboard_aggregator import AdminDashboardAggregator
from api.services.admin_dashboard_query_service import AdminDashboardQueryService
from database.db import get_session
from security.auth import Permission, require_permission

router = APIRouter(tags=["admin", "overview"])


@router.get("/overview", response_model=OverviewResponse)
async def admin_overview(
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission(Permission.ADMIN_OVERVIEW)),
):
    read = await AdminDashboardQueryService(session).load_overview()
    return AdminDashboardAggregator().build(read)

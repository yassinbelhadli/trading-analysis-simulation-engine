"""Pure DTO shaping for the existing admin overview response."""
from __future__ import annotations

from api.schemas.admin import CountsSchema, EngineStatusSchema, OverviewResponse
from api.services.admin_dashboard_query_service import AdminDashboardRead


class AdminDashboardAggregator:
    """Build the overview DTO without database access or mutations."""

    def build(self, data: AdminDashboardRead) -> OverviewResponse:
        """Preserve the existing engine override and response contract."""
        engine = dict(data.engine)
        if data.counts.active_trades > 0:
            engine["active_trades"] = data.counts.active_trades
        return OverviewResponse(
            engine=EngineStatusSchema.model_validate(engine),
            counts=CountsSchema(
                total_clients=data.counts.total_clients,
                active_subscriptions=data.counts.active_subscriptions,
                connected_accounts=data.counts.connected_accounts,
                open_support_tickets=0,
            ),
            errors_24h=data.counts.errors_24h,
        )

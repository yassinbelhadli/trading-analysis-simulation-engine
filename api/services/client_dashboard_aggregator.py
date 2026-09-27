"""Pure calculations and DTO shaping for the client dashboard."""
from __future__ import annotations

from datetime import datetime, timezone

from api.schemas.client_dashboard import (
    ClientDashboardResponse,
    DashboardLicenseDTO,
    DashboardSignalDTO,
    DashboardSubscriptionDTO,
    DashboardTodayDTO,
    DashboardTotalsDTO,
    DashboardTradeDTO,
    EquityPointDTO,
    TradingStatusDTO,
)
from api.services.client_dashboard_query_service import ClientDashboardRead


def _days_remaining(dt: datetime | None) -> int | None:
    """Return the existing UTC, clamped whole-day expiry calculation."""
    if not dt:
        return None
    delta = (dt - datetime.now(timezone.utc)).days
    return max(delta, 0)


class ClientDashboardAggregator:
    """Build the existing response without database access or mutations."""

    def build(self, data: ClientDashboardRead) -> ClientDashboardResponse:
        """Aggregate repository results into the existing client DTO."""
        user = data.user
        licenses = data.licenses
        active_license = next((license_row for license_row in licenses if license_row.status == "active"), None)
        if active_license is None and licenses:
            active_license = licenses[0]

        today_start = datetime.now(timezone.utc).replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        today_trades = [
            trade for trade in data.closed_trades
            if trade.closed_at and trade.closed_at >= today_start
        ]
        total_pnl = sum(trade.realized_pnl or 0 for trade in data.closed_trades)
        today_pnl = sum(trade.realized_pnl or 0 for trade in today_trades)
        wins = sum(1 for trade in data.closed_trades if trade.realized_pnl and trade.realized_pnl > 0)
        losses = sum(1 for trade in data.closed_trades if trade.realized_pnl and trade.realized_pnl < 0)
        win_rate = round(wins / len(data.closed_trades) * 100, 1) if data.closed_trades else 0

        gross_wins = sum(
            trade.realized_pnl
            for trade in data.closed_trades
            if trade.realized_pnl and trade.realized_pnl > 0
        )
        gross_losses = abs(sum(
            trade.realized_pnl
            for trade in data.closed_trades
            if trade.realized_pnl and trade.realized_pnl < 0
        ))
        profit_factor = round(gross_wins / gross_losses, 2) if gross_losses > 0 else (gross_wins if gross_wins else 0)

        balance = data.accounts[0].balance_snapshot if data.accounts else 0
        equity = data.accounts[0].equity_snapshot if data.accounts else balance
        active_accounts = [account for account in data.accounts if account.engine_status == "ACTIVE"]

        cumulative = 0
        equity_curve: list[EquityPointDTO] = []
        for trade in data.closed_trades[-30:]:
            cumulative += trade.realized_pnl or 0
            equity_curve.append(EquityPointDTO(
                date=trade.closed_at.isoformat() if trade.closed_at else None,
                equity=round(cumulative, 2),
            ))

        license_dto = None
        if active_license:
            license_dto = DashboardLicenseDTO(
                status=active_license.status,
                plan=active_license.plan,
                expires_at=active_license.expires_at.isoformat() if active_license.expires_at else None,
                days_remaining=_days_remaining(active_license.expires_at),
                max_accounts=active_license.max_accounts,
                used_accounts=len([
                    account for account in data.accounts
                    if account.license_id == active_license.id
                ]),
            )

        subscription_dto = None
        if user.subscription:
            subscription_dto = DashboardSubscriptionDTO(
                plan=user.subscription.plan,
                active=bool(user.subscription.active),
                billing_cycle=user.subscription.billing_cycle,
                renew_date=user.subscription.end_date.isoformat() if user.subscription.end_date else None,
                days_remaining=_days_remaining(user.subscription.end_date),
            )

        return ClientDashboardResponse(
            welcome_name=user.first_name or user.email or "Trader",
            license=license_dto,
            subscription=subscription_dto,
            trading_status=TradingStatusDTO(
                running=len(active_accounts) > 0,
                mt5_connected=len(data.accounts) > 0,
                telegram_connected=user.telegram_id is not None,
                accounts_count=len(data.accounts),
            ),
            today=DashboardTodayDTO(
                profit=round(today_pnl, 2),
                win_rate=win_rate,
                open_trades=len(data.open_trades),
                closed_trades=len(today_trades),
            ),
            totals=DashboardTotalsDTO(
                balance=round(balance or 0, 2),
                equity=round(equity or 0, 2),
                total_pnl=round(total_pnl, 2),
                total_trades=len(data.closed_trades),
                profit_factor=profit_factor,
            ),
            recent_signals=[DashboardSignalDTO(
                id=trade.id,
                symbol=trade.symbol,
                direction=trade.direction,
                entry_price=trade.entry_price,
                stop_loss=trade.stop_loss,
                take_profit=trade.take_profit,
                created_at=trade.created_at.isoformat() if trade.created_at else None,
            ) for trade in data.recent_signals],
            recent_trades=[DashboardTradeDTO(
                id=trade.id,
                symbol=trade.symbol,
                direction=trade.direction,
                status=trade.status,
                lot_size=trade.lot_size,
                realized_pnl=trade.realized_pnl,
                realized_r=trade.realized_r,
                close_reason=trade.close_reason,
                closed_at=trade.closed_at.isoformat() if trade.closed_at else None,
            ) for trade in data.recent_trades],
            equity_curve=equity_curve,
        )

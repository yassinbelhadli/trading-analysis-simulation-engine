"""Typed response DTOs for the existing client dashboard contract."""
from __future__ import annotations

from pydantic import BaseModel


Number = int | float


class DashboardLicenseDTO(BaseModel):
    status: str | None
    plan: str | None
    expires_at: str | None
    days_remaining: int | None
    max_accounts: int
    used_accounts: int


class DashboardSubscriptionDTO(BaseModel):
    plan: str | None
    active: bool
    billing_cycle: str | None
    renew_date: str | None
    days_remaining: int | None


class TradingStatusDTO(BaseModel):
    running: bool
    mt5_connected: bool
    telegram_connected: bool
    accounts_count: int


class DashboardSignalDTO(BaseModel):
    id: str
    symbol: str
    direction: str
    entry_price: Number | None
    stop_loss: Number | None
    take_profit: Number | None
    created_at: str | None


class DashboardTradeDTO(BaseModel):
    id: str
    symbol: str
    direction: str
    status: str
    lot_size: Number | None
    realized_pnl: Number | None
    realized_r: Number | None
    close_reason: str | None
    closed_at: str | None


class EquityPointDTO(BaseModel):
    date: str | None
    equity: Number


class DashboardTodayDTO(BaseModel):
    profit: Number
    win_rate: Number
    open_trades: int
    closed_trades: int


class DashboardTotalsDTO(BaseModel):
    balance: Number
    equity: Number
    total_pnl: Number
    total_trades: int
    profit_factor: Number


class ClientDashboardResponse(BaseModel):
    welcome_name: str
    license: DashboardLicenseDTO | None
    subscription: DashboardSubscriptionDTO | None
    trading_status: TradingStatusDTO
    today: DashboardTodayDTO
    totals: DashboardTotalsDTO
    recent_signals: list[DashboardSignalDTO]
    recent_trades: list[DashboardTradeDTO]
    equity_curve: list[EquityPointDTO]

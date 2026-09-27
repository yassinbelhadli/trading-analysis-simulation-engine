from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------
class EngineStatusSchema(BaseModel):
    pid: Optional[int] = None
    instance_id: Optional[str] = None
    started_at: Optional[str] = None
    uptime_hours: Optional[float] = None
    status: Optional[str] = None
    cycles: Optional[int] = None
    mt5_connected: Optional[bool] = None
    heartbeat_age_sec: Optional[int] = None
    memory_mb: Optional[float] = None
    cpu_percent: Optional[float] = None
    active_trades: int = 0
    telegram_connected: Optional[bool] = None


class CountsSchema(BaseModel):
    total_clients: int = 0
    active_subscriptions: int = 0
    connected_accounts: int = 0
    open_support_tickets: int = 0


class OverviewResponse(BaseModel):
    engine: EngineStatusSchema
    counts: CountsSchema
    errors_24h: int = 0


# ---------------------------------------------------------------------------
# User Management
# ---------------------------------------------------------------------------
class UserOut(BaseModel):
    id: str
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    telegram_username: Optional[str] = None
    role: Optional[str] = None
    account_status: str = "active"
    email_verified: bool = False
    language: str = "EN"
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    licenses_count: int = 0
    accounts_count: int = 0


class UserUpdate(BaseModel):
    status: Optional[str] = None
    role_id: Optional[str] = None
    language: Optional[str] = None


class UserCreate(BaseModel):
    email: str
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role_id: str


# ---------------------------------------------------------------------------
# Role Management
# ---------------------------------------------------------------------------
class PermissionOut(BaseModel):
    id: str
    resource: str
    action: str
    description: Optional[str] = None


class RoleOut(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    is_system: bool = False
    permissions: list[PermissionOut] = []


class RoleAssign(BaseModel):
    user_id: str
    role_id: str


# ---------------------------------------------------------------------------
# Audit Logs
# ---------------------------------------------------------------------------
class AuditLogOut(BaseModel):
    id: str
    timestamp: Optional[datetime] = None
    actor: Optional[str] = None
    action: str
    resource: Optional[str] = None
    target: Optional[str] = None
    result: Optional[str] = None
    ip: Optional[str] = None
    details: Optional[dict] = None


class AuditLogFilter(BaseModel):
    actor: Optional[str] = None
    action: Optional[str] = None
    result: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    limit: int = 50
    offset: int = 0


# ---------------------------------------------------------------------------
# Paginated
# ---------------------------------------------------------------------------
class PaginatedResponse(BaseModel):
    items: list[Any]
    total: int
    limit: int
    offset: int

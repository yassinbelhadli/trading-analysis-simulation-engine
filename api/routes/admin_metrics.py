from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select, func

from database.db import async_session_factory
from database.models import User, TradingAccount, PaperTrade, AuditLog
from core_engine.health.health_monitor import health_monitor
from core_engine.engine_manager import engine_manager

admin_metrics_router = APIRouter()


@admin_metrics_router.get("/metrics")
async def get_system_metrics():
    async with async_session_factory() as session:
        user_count = await session.scalar(select(func.count(User.id)))
        account_count = await session.scalar(select(func.count(TradingAccount.id)))
        active_accounts = await session.scalar(
            select(func.count(TradingAccount.id)).where(TradingAccount.active == True)
        )
        paper_trades = await session.scalar(select(func.count(PaperTrade.id)))

        recent_errors = await session.scalar(
            select(func.count(AuditLog.id))
            .where(AuditLog.severity == "ERROR")
            .where(AuditLog.created_at >= func.now() - func.make_interval(0, 0, 0, 1))
        )

    engine_statuses = engine_manager.list_statuses()

    health = health_monitor.get_summary()

    return {
        "users": {
            "total": user_count or 0,
        },
        "accounts": {
            "total": account_count or 0,
            "active": active_accounts or 0,
        },
        "trading": {
            "paper_trades": paper_trades or 0,
        },
        "audit": {
            "recent_errors_24h": recent_errors or 0,
        },
        "engines": {
            "total": len(engine_statuses),
            "running": sum(1 for s in engine_statuses if s.state == "RUNNING"),
            "paused": sum(1 for s in engine_statuses if s.state == "PAUSED"),
            "error": sum(1 for s in engine_statuses if s.state == "ERROR"),
        },
        "health": {
            "components_total": health["components"]["total"],
            "healthy": health["components"]["healthy"],
            "warning": health["components"]["warning"],
            "error": health["components"]["error"],
        },
        "uptime_seconds": round(health["uptime_seconds"], 1),
    }

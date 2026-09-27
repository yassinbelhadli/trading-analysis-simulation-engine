from __future__ import annotations

from fastapi import APIRouter

from core_engine.health.health_monitor import health_monitor
from core_engine.engine_manager import engine_manager

admin_health_router = APIRouter()


@admin_health_router.get("/health")
async def get_admin_health():
    return health_monitor.get_json()


@admin_health_router.get("/health/summary")
async def get_admin_health_summary():
    engine_statuses = [s for s in engine_manager.list_statuses()]
    summary = health_monitor.get_summary()
    summary["engines"] = {
        "total": len(engine_statuses),
        "running": sum(1 for s in engine_statuses if s.state == "RUNNING"),
        "paused": sum(1 for s in engine_statuses if s.state == "PAUSED"),
        "error": sum(1 for s in engine_statuses if s.state == "ERROR"),
        "stopped": sum(1 for s in engine_statuses if s.state in ("STOPPED", "DISABLED")),
    }
    return summary


@admin_health_router.get("/health/engines")
async def get_admin_engine_statuses():
    statuses = engine_manager.list_statuses()
    return [
        {
            "account_id": s.account_id,
            "state": s.state,
            "uptime_seconds": round(s.uptime_seconds, 1),
            "error": s.error,
            "last_heartbeat": s.last_heartbeat,
        }
        for s in statuses
    ]

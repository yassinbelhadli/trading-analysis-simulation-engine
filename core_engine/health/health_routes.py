"""
FastAPI router for /health endpoint.

Mount this in the main app:
    app.include_router(health_router, prefix="/api", tags=["health"])
"""

from __future__ import annotations

from fastapi import APIRouter

from core_engine.health.health_monitor import health_monitor

health_router = APIRouter()


@health_router.get("/health")
async def get_health():
    return health_monitor.get_json()


@health_router.get("/health/summary")
async def get_health_summary():
    return health_monitor.get_summary()


@health_router.get("/health/metrics")
async def get_health_metrics():
    return health_monitor.get_metrics().to_dict()

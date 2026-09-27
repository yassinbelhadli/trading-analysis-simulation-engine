from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.admin_health_service import admin_health_service
from database.db import get_session
from security.auth import Permission, log_event, require_permission

router = APIRouter(tags=["admin", "system"])


@router.get("/system-health")
async def system_health(_=Depends(require_permission(Permission.SYSTEM_HEALTH_READ))):
    return admin_health_service.get_health_json()


@router.get("/system-health/summary")
async def system_health_summary(_=Depends(require_permission(Permission.SYSTEM_HEALTH_READ))):
    return admin_health_service.get_health_summary()


@router.get("/system-health/engines")
async def system_engines(_=Depends(require_permission(Permission.SYSTEM_HEALTH_READ))):
    return admin_health_service.get_engines()


@router.get("/system-health/heartbeat")
async def system_heartbeat(_=Depends(require_permission(Permission.SYSTEM_HEALTH_READ))):
    return admin_health_service.get_heartbeat()


@router.get("/system-health/report")
async def system_health_report(_=Depends(require_permission(Permission.SYSTEM_HEALTH_READ))):
    return admin_health_service.get_health_report()


@router.get("/system-health/integrations")
async def system_health_integrations(_=Depends(require_permission(Permission.SYSTEM_HEALTH_READ))):
    """Phase 6.0 integration component registry (email/telegram/billing/news/engine)."""
    return admin_health_service.get_integrations()


@router.post("/system-health/engine/restart")
async def engine_restart(
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission(Permission.ENGINE_RESTART)),
):
    result = await admin_health_service.control_engine("restart")
    audit_id = await log_event(session, "engine.restart", "Engine restart requested",
                                user_id=current_user.id)
    await session.commit()
    return {"success": True, "audit_id": audit_id, "message": result}


@router.post("/system-health/engine/stop")
async def engine_stop(
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission(Permission.ENGINE_STOP)),
):
    result = await admin_health_service.control_engine("stop")
    audit_id = await log_event(session, "engine.stop", "Engine stop requested",
                                user_id=current_user.id)
    await session.commit()
    return {"success": True, "audit_id": audit_id, "message": result}


@router.post("/system-health/engine/start")
async def engine_start(
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission(Permission.ENGINE_START)),
):
    result = await admin_health_service.control_engine("start")
    audit_id = await log_event(session, "engine.start", "Engine start requested",
                                user_id=current_user.id)
    await session.commit()
    return {"success": True, "audit_id": audit_id, "message": result}


@router.post("/system-health/telegram/restart")
async def telegram_restart(
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission(Permission.SYSTEM_SETTINGS)),
):
    result = admin_health_service.restart_service("telegram")
    audit_id = await log_event(session, "telegram.restart", "Telegram restart requested",
                                user_id=current_user.id)
    await session.commit()
    return {"success": True, "audit_id": audit_id, "supported": result["supported"],
            "message": result["message"]}


@router.post("/system-health/mt5/restart")
async def mt5_restart(
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission(Permission.SYSTEM_SETTINGS)),
):
    result = admin_health_service.restart_service("mt5")
    audit_id = await log_event(session, "mt5.restart", "MT5 bridge restart requested",
                                user_id=current_user.id)
    await session.commit()
    return {"success": True, "audit_id": audit_id, "supported": result["supported"],
            "message": result["message"]}


@router.post("/system-health/api/restart")
async def api_restart(
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission(Permission.SYSTEM_SETTINGS)),
):
    result = admin_health_service.restart_service("api")
    audit_id = await log_event(session, "api.restart", "API restart requested",
                                user_id=current_user.id)
    await session.commit()
    return {"success": True, "audit_id": audit_id, "supported": result["supported"],
            "message": result["message"]}

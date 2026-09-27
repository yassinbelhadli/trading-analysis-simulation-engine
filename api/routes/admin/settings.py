from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import get_session
from database.models import User
from security.auth import Permission, log_event, require_permission
from api.services.site_settings import (
    SETTINGS_SCHEMA,
    get_effective_settings,
    get_settings_schema,
    update_settings,
)

router = APIRouter(prefix="/settings", tags=["admin", "settings"])

_SECRET_KEYS = {s["key"] for s in SETTINGS_SCHEMA if s.get("is_secret")}


class SettingsUpdate(BaseModel):
    updates: Dict[str, Any]


@router.get("/schema")
async def settings_schema(
    _user: User = Depends(require_permission(Permission.SYSTEM_SETTINGS)),
):
    return get_settings_schema()


@router.get("")
async def get_settings(
    _user: User = Depends(require_permission(Permission.SYSTEM_SETTINGS)),
    session: AsyncSession = Depends(get_session),
):
    """Effective settings. Secret values are masked (never returned)."""
    effective = await get_effective_settings(session, decrypt_secrets=False)
    public = {}
    for key, value in effective.items():
        if key in _SECRET_KEYS:
            public[key] = "••••••••"
        else:
            public[key] = value
    return {"settings": public}


@router.put("")
async def put_settings(
    body: SettingsUpdate,
    current_user: User = Depends(require_permission(Permission.SYSTEM_SETTINGS)),
    session: AsyncSession = Depends(get_session),
):
    if not body.updates:
        raise HTTPException(status_code=400, detail="No settings provided")
    try:
        saved = await update_settings(session, body.updates, actor_id=current_user.id)
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await log_event(
        session,
        "settings.update",
        f"Settings updated: {', '.join(sorted(saved.keys()))}",
        user_id=current_user.id,
        severity="INFO",
        payload={"keys": sorted(saved.keys())},
        commit=True,
    )
    effective = await get_effective_settings(session, decrypt_secrets=True)
    return {"success": True, "updated": list(saved.keys()), "settings": effective}

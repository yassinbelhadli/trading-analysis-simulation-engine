"""Client EA download + version checking (Sprint 2).

Downloads are gated on a valid, non-expired license. Build artifacts are served
from storage/ea/ (path stored on the EABuild row).
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import get_session
from database.models import EABuild, License
from security.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/client/ea", tags=["client-ea"])

EA_STORAGE_DIR = Path(__file__).resolve().parents[3] / "storage" / "ea"


def _version_key(version: str) -> tuple:
    parts = []
    for seg in str(version).replace("v", "").split("."):
        try:
            parts.append(int(seg))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def _build_payload(b: EABuild, storage_exists: bool = True) -> dict:
    return {
        "id": b.id,
        "version": b.version,
        "release_notes": b.release_notes,
        "changelog": b.changelog,
        "released_at": b.released_at.isoformat() if b.released_at else None,
        "windows_available": bool(b.windows_file),
        "macos_available": bool(b.macos_file),
    }


async def _latest_build(session: AsyncSession) -> Optional[EABuild]:
    result = await session.execute(
        select(EABuild).where(EABuild.is_latest == True, EABuild.approved == True)
    )
    b = result.scalar_one_or_none()
    if b:
        return b
    result = await session.execute(
        select(EABuild)
        .where(EABuild.approved == True)
        .order_by(EABuild.released_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _find_active_license(session: AsyncSession, user_id: str) -> Optional[License]:
    from datetime import datetime, timezone
    result = await session.execute(
        select(License).where(License.user_id == user_id).order_by(License.created_at.desc())
    )
    for lic in result.scalars().all():
        if lic.status == "active" and (lic.expires_at is None or lic.expires_at >= datetime.now(timezone.utc)):
            return lic
    return None


@router.get("")
async def client_ea_info(
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Latest EA version + full changelog."""
    result = await session.execute(
        select(EABuild).where(EABuild.approved == True).order_by(EABuild.released_at.desc())
    )
    builds = list(result.scalars().all())
    latest = await _latest_build(session)
    return {
        "latest": _build_payload(latest) if latest else None,
        "changelog": [_build_payload(b) for b in builds],
        "total": len(builds),
    }


@router.post("/check-updates")
async def client_ea_check_updates(
    body: dict,
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Compare the client's installed version with the latest release."""
    current_version = str(body.get("current_version") or "").strip()
    latest = await _latest_build(session)
    if latest is None:
        return {"update_available": False, "current_version": current_version or None,
                "latest_version": None}
    update_available = bool(current_version) and _version_key(current_version) < _version_key(latest.version)
    return {
        "update_available": update_available,
        "current_version": current_version or None,
        "latest_version": latest.version,
    }


@router.get("/download/latest")
async def client_ea_download_latest(
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _serve_build(session, current_user, None)


@router.get("/download/{build_id}")
async def client_ea_download(
    build_id: str,
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _serve_build(session, current_user, build_id)


async def _serve_build(session: AsyncSession, current_user, build_id: Optional[str]):
    lic = await _find_active_license(session, current_user.id)
    if lic is None:
        raise HTTPException(status_code=403, detail="Invalid or expired license")

    if build_id:
        result = await session.execute(
            select(EABuild).where(
                (EABuild.id == build_id) | (EABuild.version == build_id),
                EABuild.approved == True,
            )
        )
        build = result.scalars().first()
    else:
        build = await _latest_build(session)
    if build is None:
        raise HTTPException(status_code=404, detail="Build not found")

    if not build.windows_file:
        raise HTTPException(status_code=404, detail="No Windows build file available for this version")

    file_path = EA_STORAGE_DIR / build.windows_file
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Build file not found on server")

    return FileResponse(
        path=file_path,
        # Serve the real stored artifact name so the client receives the
        # correct extension (e.g. .zip, .exe, .pdf) — never a forced .ex5.
        filename=build.windows_file,
        media_type="application/octet-stream",
    )

"""Admin EA build publishing (completes the Sprint 2 EA distribution gap).

Admin/owner workflow for publishing Expert Advisor releases: list, create,
multipart upload of the compiled .ex4/.ex5 artifact, latest-release
management, metadata patch, and delete.

The client download side (api/routes/client/ea.py) reads the SAME EABuild
table and SAME storage/ea/ directory — this router is the publishing half of
one shared source of truth. Download authorization (active, non-expired
license) is untouched and enforced in the client router.

File safety:
  - only .ex4/.ex5 extensions are accepted (MetaTrader compiled EAs);
  - size floor (blocks the 25-byte placeholder stub) and hard cap enforced;
  - the artifact is stored with a version-derived, path-safe filename;
  - delete removes the DB row first, then the file (best-effort after commit).
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import get_session
from database.models import EABuild
from security.auth import Permission, log_event, require_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ea-builds", tags=["admin", "ea-builds"])

# Same convention as api/routes/client/ea.py (repo_root / storage / ea).
EA_STORAGE_DIR = Path(__file__).resolve().parents[3] / "storage" / "ea"

# Version contract mirrors client _version_key() in api/routes/client/ea.py.
_VERSION_RE = re.compile(r"^[vV]?(\d+(\.\d+){1,4})$")

# Artifact contract: compiled MetaTrader Expert Advisors + common safe file types.
_ALLOWED_EXTENSIONS = {".ex4", ".ex5", ".exe", ".msi", ".zip", ".pdf", ".dmg", ".apk", ".ipa"}
MIN_EA_FILE_BYTES = 1 * 1024 * 1024  # 1 MB minimum
MAX_EA_FILE_BYTES = int(1.5 * 1024 * 1024 * 1024)  # 1.5 GB maximum


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _normalize_version(raw: str) -> str:
    """Accept '1.2.0' or 'v1.2.0'; store without the leading 'v'."""
    match = _VERSION_RE.match(raw or "")
    if not match:
        raise HTTPException(
            status_code=400,
            detail="Version must be a dotted numeric string like '1.2.0'",
        )
    return match.group(1)


def _artifact_name(version: str, ext: str = ".ex5") -> str:
    """Path-safe, version-derived filename (windows_file column value).

    Preserves the uploaded extension so clients receive the real artifact
    type (e.g. .zip, .exe, .pdf) instead of a forced .ex5 name.
    """
    safe_ext = ext.lower()
    if not safe_ext.startswith("."):
        safe_ext = f".{safe_ext}"
    return f"ict_ea_v{version}{safe_ext}"


async def _get_build(session: AsyncSession, build_id: str) -> EABuild:
    result = await session.execute(
        select(EABuild).where((EABuild.id == build_id) | (EABuild.version == build_id))
    )
    build = result.scalars().first()
    if build is None:
        raise HTTPException(status_code=404, detail="Build not found")
    return build


def _payload(build: EABuild) -> dict:
    windows_file = build.windows_file
    file_on_disk = False
    if windows_file:
        file_on_disk = (EA_STORAGE_DIR / windows_file).exists()
    return {
        "id": build.id,
        "version": build.version,
        "release_notes": build.release_notes,
        "changelog": build.changelog,
        "released_at": build.released_at.isoformat() if build.released_at else None,
        "windows_available": bool(windows_file) and file_on_disk,
        "macos_available": bool(build.macos_file),
        "is_latest": bool(build.is_latest),
        "windows_file": windows_file,
        "approved": bool(build.approved),
        "approved_by": build.approved_by,
        "approved_at": build.approved_at.isoformat() if build.approved_at else None,
        "rejection_reason": build.rejection_reason,
    }


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------
@router.get("")
async def list_ea_builds(
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission(Permission.EA_READ)),
):
    """List all EA releases, newest first."""
    result = await session.execute(select(EABuild).order_by(EABuild.released_at.desc()))
    builds = result.scalars().all()
    return {"items": [_payload(b) for b in builds], "total": len(builds)}


# ---------------------------------------------------------------------------
# Create release (metadata only — artifact upload is a separate step)
# ---------------------------------------------------------------------------
@router.post("")
async def create_ea_build(
    body: dict,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission(Permission.EA_PUBLISH)),
):
    version = _normalize_version(body.get("version"))
    release_notes = (body.get("release_notes") or "").strip() or None
    changelog = (body.get("changelog") or "").strip() or None

    result = await session.execute(select(EABuild).where(EABuild.version == version))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail=f"Version {version} already exists")

    build = EABuild(
        version=version,
        release_notes=release_notes,
        changelog=changelog,
        is_latest=False,
    )
    session.add(build)
    await session.flush()
    audit_id = await log_event(
        session,
        "ea_build.created",
        f"EA release v{version} created",
        user_id=current_user.id,
        payload={"build_id": build.id, "version": version},
    )
    await session.commit()
    return {
        "id": build.id,
        "version": build.version,
        "audit_id": audit_id,
        "message": f"Release v{version} created",
    }


# ---------------------------------------------------------------------------
# Multipart artifact upload
# ---------------------------------------------------------------------------
@router.post("/{build_id}/upload")
async def upload_ea_build(
    build_id: str,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission(Permission.EA_PUBLISH)),
):
    build = await _get_build(session, build_id)

    ext = Path(file.filename or "").suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(_ALLOWED_EXTENSIONS))
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext or 'none'}' not allowed. Accepted: {allowed}",
        )

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(data) < MIN_EA_FILE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File is too small ({len(data)} bytes). Minimum is 1 MB",
        )
    if len(data) > MAX_EA_FILE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds the 1.5 GB upload limit",
        )

    artifact_name = _artifact_name(build.version, ext)
    target = EA_STORAGE_DIR / artifact_name
    tmp = EA_STORAGE_DIR / f"{artifact_name}.tmp"
    try:
        EA_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        tmp.write_bytes(data)
        if target.exists():
            target.unlink()
        tmp.replace(target)
    except OSError as exc:
        logger.error("ea_build upload: could not store artifact %s: %s", artifact_name, exc)
        raise HTTPException(status_code=500, detail="Could not store build file on server")

    build.windows_file = artifact_name
    try:
        await session.commit()
    except Exception:
        # Keep disk consistent with the DB — never leave an orphaned file that
        # the client API would treat as an available build.
        target.unlink(missing_ok=True)
        raise

    audit_id = await log_event(
        session,
        "ea_build.uploaded",
        f"EA release v{build.version} artifact uploaded ({len(data)} bytes)",
        user_id=current_user.id,
        payload={"build_id": build.id, "version": build.version, "size_bytes": len(data)},
    )
    await session.commit()
    return {
        "success": True,
        "id": build.id,
        "version": build.version,
        "windows_file": artifact_name,
        "size_bytes": len(data),
        "audit_id": audit_id,
        "message": f"Build file for v{build.version} published",
    }


# ---------------------------------------------------------------------------
# Latest-release management
# ---------------------------------------------------------------------------
@router.post("/{build_id}/set-latest")
async def set_latest_ea_build(
    build_id: str,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission(Permission.EA_PUBLISH)),
):
    build = await _get_build(session, build_id)

    result = await session.execute(select(EABuild))
    for other in result.scalars().all():
        other.is_latest = False
    build.is_latest = True
    await session.flush()
    audit_id = await log_event(
        session,
        "ea_build.set_latest",
        f"EA release v{build.version} marked as latest",
        user_id=current_user.id,
        payload={"build_id": build.id, "version": build.version},
    )
    await session.commit()
    return {
        "success": True,
        "id": build.id,
        "version": build.version,
        "is_latest": True,
        "audit_id": audit_id,
        "message": f"v{build.version} is now the latest release",
    }


# ---------------------------------------------------------------------------
# Patch metadata (version is immutable — it is the client-facing identifier
# and the artifact filename embeds it)
# ---------------------------------------------------------------------------
@router.patch("/{build_id}")
async def update_ea_build(
    build_id: str,
    body: dict,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission(Permission.EA_PUBLISH)),
):
    build = await _get_build(session, build_id)

    if "release_notes" in body:
        build.release_notes = (body.get("release_notes") or "").strip() or None
    if "changelog" in body:
        build.changelog = (body.get("changelog") or "").strip() or None

    audit_id = await log_event(
        session,
        "ea_build.updated",
        f"EA release v{build.version} metadata updated",
        user_id=current_user.id,
        payload={"build_id": build.id, "version": build.version},
    )
    await session.commit()
    return {
        "success": True,
        "id": build.id,
        "version": build.version,
        "audit_id": audit_id,
        "message": "Release updated",
    }


# ---------------------------------------------------------------------------
# Delete (DB row first; artifact removed best-effort after commit)
# ---------------------------------------------------------------------------
@router.delete("/{build_id}")
async def delete_ea_build(
    build_id: str,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission(Permission.EA_PUBLISH)),
):
    build = await _get_build(session, build_id)
    version = build.version
    artifact = build.windows_file

    await session.delete(build)
    await session.commit()

    deleted_file = False
    if artifact:
        target = EA_STORAGE_DIR / artifact
        try:
            if target.exists():
                target.unlink()
                deleted_file = True
        except OSError as exc:
            logger.warning("ea_build delete: could not remove %s: %s", artifact, exc)

    audit_id = await log_event(
        session,
        "ea_build.deleted",
        f"EA release v{version} deleted",
        user_id=current_user.id,
        payload={"build_id": build.id, "version": version, "file_removed": deleted_file},
    )
    await session.commit()
    return {
        "success": True,
        "version": version,
        "file_removed": deleted_file,
        "audit_id": audit_id,
        "message": f"Release v{version} deleted",
    }


# ---------------------------------------------------------------------------
# Approve / Reject (approval workflow)
# ---------------------------------------------------------------------------
@router.post("/{build_id}/approve")
async def approve_ea_build(
    build_id: str,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission(Permission.EA_PUBLISH)),
):
    """Approve a build so clients can see and download it."""
    from datetime import datetime, timezone
    build = await _get_build(session, build_id)
    if build.approved:
        return {"success": True, "message": "Build is already approved"}

    build.approved = True
    build.approved_by = current_user.id
    build.approved_at = datetime.now(timezone.utc)
    build.rejection_reason = None

    audit_id = await log_event(
        session,
        "ea_build.approved",
        f"EA release v{build.version} approved for client access",
        user_id=current_user.id,
        payload={"build_id": build.id, "version": build.version},
    )
    await session.commit()
    return {
        "success": True,
        "id": build.id,
        "version": build.version,
        "audit_id": audit_id,
        "message": f"Release v{build.version} approved",
    }


@router.post("/{build_id}/reject")
async def reject_ea_build(
    build_id: str,
    body: dict,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission(Permission.EA_PUBLISH)),
):
    """Reject a build — clients will not see it."""
    build = await _get_build(session, build_id)
    reason = (body.get("reason") or "").strip() or None

    build.approved = False
    build.approved_by = current_user.id
    build.approved_at = None
    build.rejection_reason = reason

    audit_id = await log_event(
        session,
        "ea_build.rejected",
        f"EA release v{build.version} rejected",
        user_id=current_user.id,
        payload={"build_id": build.id, "version": build.version, "reason": reason},
    )
    await session.commit()
    return {
        "success": True,
        "id": build.id,
        "version": build.version,
        "audit_id": audit_id,
        "message": f"Release v{build.version} rejected",
    }

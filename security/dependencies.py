from __future__ import annotations

import logging
from typing import Callable, Optional

from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import get_session
from database.models import AuditLog, LoginSession, User
from security.jwt_handler import decode_token

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


# ---------------------------------------------------------------------------
# Token extraction  (header → cookie fallback)
# ---------------------------------------------------------------------------
def _extract_token(request: Request) -> Optional[str]:
    token = request.headers.get("Authorization")
    if token and token.startswith("Bearer "):
        return token[7:]
    return request.cookies.get("access_token")


# ---------------------------------------------------------------------------
# get_current_user  (dependency)
# ---------------------------------------------------------------------------
async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> User:
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if user.account_status != "active":
        raise HTTPException(status_code=403, detail="Account is not active")
    return user


# ---------------------------------------------------------------------------
# get_optional_user  (returns None instead of 401)
# ---------------------------------------------------------------------------
async def get_optional_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> Optional[User]:
    token = _extract_token(request)
    if not token:
        return None
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            return None
        result = await session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# require_permission  (dependency factory with audit logging)
# ---------------------------------------------------------------------------
def require_permission(permission: str) -> Callable:
    from security.access_control import has_permission

    async def dependency(
        request: Request,
        current_user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_session),
    ):
        if await has_permission(session, current_user, permission):
            return current_user

        ip = request.client.host if request.client else "unknown"
        session.add(AuditLog(
            user_id=current_user.id,
            event_type="access.denied",
            severity="WARNING",
            source="web",
            message=f"ACCESS_DENIED | {permission} | {request.method} {request.url.path}",
            payload_json={
                "permission": permission,
                "method": request.method,
                "path": request.url.path,
                "ip": ip,
            },
        ))
        await session.commit()
        raise HTTPException(status_code=403, detail=f"Missing permission: {permission}")

    return dependency


# ---------------------------------------------------------------------------
# get_current_admin_user  (convenience with audit logging)
# ---------------------------------------------------------------------------
async def get_current_admin_user(
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> User:
    if current_user.role_rel and current_user.role_rel.name in ("owner", "admin"):
        return current_user

    ip = request.client.host if request.client else "unknown"
    session.add(AuditLog(
        user_id=current_user.id,
        event_type="access.denied",
        severity="WARNING",
        source="web",
        message=f"ACCESS_DENIED | admin_required | {request.method} {request.url.path}",
        payload_json={"method": request.method, "path": request.url.path, "ip": ip},
    ))
    await session.commit()
    raise HTTPException(status_code=403, detail="Admin access required")


# ---------------------------------------------------------------------------
# require_role  (dependency factory — simpler sibling of require_permission)
# ---------------------------------------------------------------------------
def require_role(role_name: str) -> Callable:
    async def dependency(
        request: Request,
        current_user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_session),
    ):
        if current_user.role_rel and current_user.role_rel.name == role_name:
            return current_user

        ip = request.client.host if request.client else "unknown"
        session.add(AuditLog(
            user_id=current_user.id,
            event_type="access.denied",
            severity="WARNING",
            source="web",
            message=f"ACCESS_DENIED | role:{role_name} | {request.method} {request.url.path}",
            payload_json={"required_role": role_name, "method": request.method,
                          "path": request.url.path, "ip": ip},
        ))
        await session.commit()
        raise HTTPException(status_code=403, detail=f"Role '{role_name}' required")

    return dependency

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.db import get_session
from database.models import License, Role, TradingAccount, User
from shared_utils.timezone import is_valid_timezone
from security.auth import (
    Permission,
    get_hierarchy_level,
    hash_password,
    has_permission,
    log_event,
    require_permission,
)

router = APIRouter(tags=["admin", "users"])


@router.get("/users")
async def list_users(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    status: str = None,
    role: str = None,
    q: str = None,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission(Permission.USERS_READ)),
):
    query = select(User).options(
        selectinload(User.role_rel),
        selectinload(User.licenses),
        selectinload(User.accounts),
    )
    count_query = select(func.count()).select_from(User)

    if status:
        query = query.where(User.status == status)
        count_query = count_query.where(User.status == status)
    if role:
        query = query.join(Role, User.role_id == Role.id).where(Role.name == role)
        count_query = count_query.join(Role, User.role_id == Role.id).where(Role.name == role)
    if q:
        like = f"%{q}%"
        cond = (
            User.email.ilike(like)
            | User.first_name.ilike(like)
            | User.last_name.ilike(like)
        )
        query = query.where(cond)
        count_query = count_query.where(cond)

    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(User.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(query)
    users = result.scalars().all()

    return {
        "items": [
            {
                "id": u.id,
                "email": u.email,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "telegram_username": u.telegram_username,
                "role": u.role_rel.name if u.role_rel else None,
                "account_status": u.account_status,
                "email_verified": u.email_verified,
                "language": u.language,
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "last_login": u.last_login.isoformat() if u.last_login else None,
                "licenses_count": len(u.licenses) if u.licenses else 0,
                "accounts_count": len(u.accounts) if u.accounts else 0,
            }
            for u in users
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/users/{user_id}")
async def get_user(
    user_id: str,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission(Permission.USERS_READ)),
):
    result = await session.execute(
        select(User)
        .options(selectinload(User.role_rel), selectinload(User.licenses), selectinload(User.accounts))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "telegram_id": user.telegram_id,
        "telegram_username": user.telegram_username,
        "role": user.role_rel.name if user.role_rel else None,
        "role_id": user.role_id,
        "account_status": user.account_status,
        "email_verified": user.email_verified,
        "two_factor_enabled": user.two_factor_enabled,
        "language": user.language,
        "timezone": user.timezone,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "licenses": [{"id": l.id, "license_key": l.license_key, "plan": l.plan, "status": l.status} for l in (user.licenses or [])],
        "accounts_count": len(user.accounts or []),
    }


@router.patch("/users/{user_id}")
async def update_user(
    user_id: str,
    body: dict,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission(Permission.USERS_UPDATE)),
):
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if "first_name" in body:
        user.first_name = body["first_name"]
    if "last_name" in body:
        user.last_name = body["last_name"]
    if "email" in body:
        new_email = body["email"].strip().lower()
        existing = await session.execute(select(User).where(User.email == new_email, User.id != user_id))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Email already taken")
        user.email = new_email
    if "status" in body:
        user.account_status = body["status"]
    if "language" in body:
        user.language = body["language"]
    if "timezone" in body:
        tz = str(body["timezone"]).strip() if body["timezone"] else None
        if tz and not is_valid_timezone(tz):
            raise HTTPException(status_code=400, detail="Invalid timezone. Use a valid IANA timezone.")
        user.timezone = tz
    if "account_status" in body:
        user.account_status = body["account_status"]
    if "role_id" in body:
        new_role_id = body["role_id"]
        role_result = await session.execute(select(Role).where(Role.id == new_role_id))
        new_role = role_result.scalar_one_or_none()
        if not new_role:
            raise HTTPException(status_code=400, detail="Invalid role_id")
        caller_role_name = current_user.role_rel.name if current_user.role_rel else None
        # Owner accounts are provisioned via seed scripts only — no API path may
        # grant the owner role, not even to an existing owner (frozen OQ-1
        # contract; also limits blast radius of a compromised owner token).
        if new_role.name == "owner":
            raise HTTPException(status_code=403, detail="Owner accounts are provisioned via scripts only")
        # Hierarchy guard: a non-owner cannot raise a user to a role at or
        # above their own level (mirrors assign_role).
        if caller_role_name != "owner" and get_hierarchy_level(new_role.name) >= get_hierarchy_level(caller_role_name):
            raise HTTPException(status_code=403, detail="Cannot assign roles at or above your level")
        # Last-owner protection when demoting the owner.
        if user.role_rel and user.role_rel.name == "owner" and new_role.name != "owner":
            owner_count = await session.execute(
                select(User).join(Role, User.role_id == Role.id).where(Role.name == "owner")
            )
            if len(owner_count.scalars().all()) <= 1:
                raise HTTPException(status_code=403, detail="Cannot demote the last owner")
        user.role_id = body["role_id"]

    audit_id = await log_event(session, "user.updated", f"User {user_id} updated",
                                user_id=current_user.id, payload={"changes": body})
    await session.commit()
    return {"success": True, "audit_id": audit_id, "message": "User updated"}


@router.post("/users")
async def create_user(
    body: dict,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission(Permission.USERS_CREATE)),
):
    email = body.get("email", "").strip().lower()
    password = body.get("password", "")
    role_id = body.get("role_id")

    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password required")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    result = await session.execute(select(User).where(User.email == email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    if role_id:
        role_result = await session.execute(select(Role).where(Role.id == role_id))
        target_role = role_result.scalar_one_or_none()
        if not target_role:
            raise HTTPException(status_code=400, detail="Invalid role_id")
        if target_role.name == "owner":
            raise HTTPException(status_code=403, detail="Cannot create owner accounts")

    user = User(
        email=email,
        password_hash=hash_password(password),
        first_name=body.get("first_name", ""),
        last_name=body.get("last_name", ""),
        role_id=role_id,
        language="EN",
        status="active",
        account_status="active",
        email_verified=True,
    )
    session.add(user)
    await session.flush()

    audit_id = await log_event(session, "user.created", f"User {email} created",
                                user_id=current_user.id, payload={"user_id": user.id, "role_id": role_id})
    await session.commit()

    return {"id": user.id, "email": user.email, "audit_id": audit_id, "message": "User created"}


@router.post("/users/{user_id}/suspend")
async def suspend_user(
    user_id: str,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission(Permission.CLIENTS_SUSPEND)),
):
    result = await session.execute(
        select(User).options(selectinload(User.role_rel)).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role_rel and user.role_rel.name == "owner":
        raise HTTPException(status_code=403, detail="Cannot suspend an owner via API")

    user.account_status = "suspended"
    audit_id = await log_event(session, "user.suspended", f"User {user_id} suspended",
                                user_id=current_user.id)
    await session.commit()
    return {"success": True, "audit_id": audit_id, "message": "User suspended"}


@router.post("/users/{user_id}/activate")
async def activate_user(
    user_id: str,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission(Permission.CLIENTS_ACTIVATE)),
):
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.account_status = "active"
    audit_id = await log_event(session, "user.activated", f"User {user_id} activated",
                                user_id=current_user.id)
    await session.commit()
    return {"success": True, "audit_id": audit_id, "message": "User activated"}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission(Permission.USERS_DELETE)),
):
    result = await session.execute(
        select(User).options(selectinload(User.role_rel)).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    # Self-deletion guard must run before the owner guard so an owner deleting
    # their own account gets the accurate "yourself" error, not the owner one.
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    if user.role_rel and user.role_rel.name == "owner":
        raise HTTPException(status_code=403, detail="Cannot delete the last owner")

    # Soft delete only: client data is never hard-deleted (CLAUDE.md rule).
    # FK child tables (licenses, subscriptions, trading_accounts, ...) have no
    # ON CASCADE, so a hard delete would crash with IntegrityError anyway.
    user.account_status = "deleted"
    user.status = "deleted"
    now = datetime.now(timezone.utc)
    for login_session in user.sessions:
        if login_session.is_active:
            login_session.is_active = False
            login_session.revoked_at = now

    audit_id = await log_event(session, "user.deleted", f"User {user_id} deactivated",
                                user_id=current_user.id,
                                payload={"soft_delete": True})
    await session.commit()
    return {"success": True, "audit_id": audit_id, "message": "User deactivated"}

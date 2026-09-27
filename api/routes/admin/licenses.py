from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import get_session
from database.models import License, TradingAccount, User
from security.auth import Permission, log_event, require_permission
from api.services.plans_config import get_plan

router = APIRouter(tags=["admin", "licenses"])


@router.get("/licenses")
async def list_licenses(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    status: str = None,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission(Permission.LICENSES_READ)),
):
    query = select(License).options(
        # relationship loading handled by selectinload on the model
    ).order_by(License.created_at.desc())
    count_query = select(func.count()).select_from(License)
    if status:
        query = query.where(License.status == status)
        count_query = count_query.where(License.status == status)
    total = (await session.execute(count_query)).scalar() or 0
    query = query.offset(offset).limit(limit)
    result = await session.execute(query)
    licenses = result.scalars().all()

    # Fetch user emails/usernames in batch
    user_ids = [l.user_id for l in licenses]
    if user_ids:
        user_result = await session.execute(
            select(User).where(User.id.in_(user_ids))
        )
        users_map = {u.id: u for u in user_result.scalars().all()}
    else:
        users_map = {}

    return {
        "items": [
            {
                "id": l.id,
                "user_id": l.user_id,
                "license_key": l.license_key,
                "plan": l.plan,
                "plan_name": (get_plan(l.plan) or {}).get("name", l.plan),
                "features": (get_plan(l.plan) or {}).get("features", {}),
                "status": l.status,
                "max_accounts": l.max_accounts,
                "expires_at": l.expires_at.isoformat() if l.expires_at else None,
                "bound_account_id": l.bound_account_id,
                "bound_at": l.bound_at.isoformat() if l.bound_at else None,
                "telegram_id": l.telegram_id,
                "transfer_locked": l.transfer_locked,
                "created_at": l.created_at.isoformat() if l.created_at else None,
                "user_email": users_map[l.user_id].email if l.user_id in users_map else None,
                "telegram_username": users_map[l.user_id].telegram_username if l.user_id in users_map else None,
            }
            for l in licenses
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/licenses/{license_id}")
async def get_license(
    license_id: str,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission(Permission.LICENSES_READ)),
):
    result = await session.execute(select(License).where(License.id == license_id))
    lic = result.scalar_one_or_none()
    if not lic:
        raise HTTPException(status_code=404, detail="License not found")
    return {
        "id": lic.id,
        "user_id": lic.user_id,
        "license_key": lic.license_key,
        "plan": lic.plan,
        "plan_name": (get_plan(lic.plan) or {}).get("name", lic.plan),
        "features": (get_plan(lic.plan) or {}).get("features", {}),
        "status": lic.status,
        "max_accounts": lic.max_accounts,
        "expires_at": lic.expires_at.isoformat() if lic.expires_at else None,
        "bound_account_id": lic.bound_account_id,
        "bound_at": lic.bound_at.isoformat() if lic.bound_at else None,
        "telegram_id": lic.telegram_id,
        "transfer_locked": lic.transfer_locked,
        "created_at": lic.created_at.isoformat() if lic.created_at else None,
    }


@router.post("/licenses")
async def create_license(
    body: dict,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission(Permission.LICENSES_CREATE)),
):
    user_id = body.get("user_id", "").strip()
    plan = body.get("plan", "starter")
    max_accounts = int(body.get("max_accounts", 1))
    expires_in_days = body.get("expires_in_days")

    if not user_id:
        raise HTTPException(status_code=400, detail="user_id required")

    user_result = await session.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    from security.license_gen import generate_license_key
    key = generate_license_key()
    expires_at = None
    if expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=int(expires_in_days))

    lic = License(
        user_id=user.id,
        license_key=key,
        plan=plan,
        max_accounts=max_accounts,
        expires_at=expires_at,
        status="active",
    )
    session.add(lic)
    await session.flush()

    audit_id = await log_event(session, "license.created", f"License {key} created for {user_id}",
                                user_id=current_user.id, payload={"plan": plan, "license_id": lic.id})
    await session.commit()

    return {
        "id": lic.id,
        "license_key": lic.license_key,
        "plan": lic.plan,
        "status": lic.status,
        "expires_at": lic.expires_at.isoformat() if lic.expires_at else None,
        "audit_id": audit_id,
        "message": "License created",
    }


@router.patch("/licenses/{license_id}")
async def update_license(
    license_id: str,
    body: dict,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission(Permission.LICENSES_UPDATE)),
):
    result = await session.execute(select(License).where(License.id == license_id))
    lic = result.scalar_one_or_none()
    if not lic:
        raise HTTPException(status_code=404, detail="License not found")
    if "plan" in body:
        lic.plan = body["plan"]
    if "status" in body:
        lic.status = body["status"]
    if "max_accounts" in body:
        lic.max_accounts = int(body["max_accounts"])
    audit_id = await log_event(session, "license.updated", f"License {license_id} updated",
                                user_id=current_user.id, payload={"changes": body})
    await session.commit()
    return {"success": True, "audit_id": audit_id, "message": "License updated"}


@router.post("/licenses/{license_id}/activate")
async def activate_license(
    license_id: str,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission(Permission.LICENSES_UPDATE)),
):
    result = await session.execute(select(License).where(License.id == license_id))
    lic = result.scalar_one_or_none()
    if not lic:
        raise HTTPException(status_code=404, detail="License not found")
    lic.status = "active"
    audit_id = await log_event(session, "license.activated", f"License {license_id} activated",
                                user_id=current_user.id)
    await session.commit()
    try:
        from api.services.email_service import send_license_activated_email
        from database.models import User
        owner = await session.get(User, lic.user_id)
        if owner and owner.email:
            await send_license_activated_email(
                owner.email, owner.first_name or owner.email, lic.license_key or license_id,
                session=session,
            )
    except Exception:
        pass
    return {"success": True, "audit_id": audit_id, "message": "License activated"}


@router.post("/licenses/{license_id}/deactivate")
async def deactivate_license(
    license_id: str,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission(Permission.LICENSES_UPDATE)),
):
    result = await session.execute(select(License).where(License.id == license_id))
    lic = result.scalar_one_or_none()
    if not lic:
        raise HTTPException(status_code=404, detail="License not found")
    lic.status = "inactive"
    audit_id = await log_event(session, "license.deactivated", f"License {license_id} deactivated",
                                user_id=current_user.id)
    await session.commit()
    return {"success": True, "audit_id": audit_id, "message": "License deactivated"}


@router.post("/licenses/{license_id}/unbind")
async def unbind_license(
    license_id: str,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission(Permission.LICENSES_UPDATE)),
):
    result = await session.execute(select(License).where(License.id == license_id))
    lic = result.scalar_one_or_none()
    if not lic:
        raise HTTPException(status_code=404, detail="License not found")
    lic.telegram_id = None
    lic.bound_at = None
    lic.bound_account_id = None
    lic.status = "active"
    audit_id = await log_event(session, "license.unbound", f"License {license_id} unbound",
                                user_id=current_user.id)
    await session.commit()
    return {"success": True, "audit_id": audit_id, "message": "License unbound"}


@router.post("/licenses/{license_id}/reset")
async def reset_license(
    license_id: str,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission(Permission.LICENSES_UPDATE)),
):
    result = await session.execute(select(License).where(License.id == license_id))
    lic = result.scalar_one_or_none()
    if not lic:
        raise HTTPException(status_code=404, detail="License not found")
    lic.telegram_id = None
    lic.bound_at = None
    lic.bound_account_id = None
    lic.transfer_locked = False
    lic.status = "active"
    audit_id = await log_event(session, "license.reset", f"License {license_id} reset",
                                user_id=current_user.id)
    await session.commit()
    return {"success": True, "audit_id": audit_id, "message": "License reset"}


@router.delete("/licenses/{license_id}")
async def delete_license(
    license_id: str,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission(Permission.LICENSES_DELETE)),
):
    result = await session.execute(select(License).where(License.id == license_id))
    lic = result.scalar_one_or_none()
    if not lic:
        raise HTTPException(status_code=404, detail="License not found")
    if lic.bound_account_id:
        raise HTTPException(status_code=400, detail="License is bound to an account. Unbind first.")
    await session.delete(lic)
    audit_id = await log_event(session, "license.deleted", f"License {license_id} deleted",
                                user_id=current_user.id)
    await session.commit()
    return {"success": True, "audit_id": audit_id, "message": "License deleted"}

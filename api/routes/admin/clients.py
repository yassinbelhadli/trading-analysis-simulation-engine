from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.db import get_session
from database.models import License, Subscription, TradingAccount, User
from security.auth import Permission, require_permission

router = APIRouter(tags=["admin", "clients"])


@router.get("/clients")
async def list_clients(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    status: str = None,
    q: str = None,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission(Permission.CLIENTS_READ)),
):
    query = (
        select(User)
        .options(selectinload(User._subscriptions), selectinload(User.accounts), selectinload(User.licenses))
        .order_by(User.created_at.desc())
    )
    count_query = select(func.count()).select_from(User)

    if status:
        query = query.where(User.account_status == status)
        count_query = count_query.where(User.account_status == status)
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

    query = query.offset(offset).limit(limit)
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
                "account_status": u.account_status,
                "subscription_plan": u.subscription.plan if u.subscription else None,
                "subscription_active": u.subscription.active if u.subscription else False,
                "accounts_count": len(u.accounts or []),
                "licenses_count": len(u.licenses or []),
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "last_login": u.last_login.isoformat() if u.last_login else None,
            }
            for u in users
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/clients/{client_id}")
async def get_client(
    client_id: str,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission(Permission.CLIENTS_READ)),
):
    result = await session.execute(
        select(User)
        .options(
            selectinload(User._subscriptions),
            selectinload(User.accounts),
            selectinload(User.licenses),
        )
        .where(User.id == client_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Client not found")

    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "telegram_id": user.telegram_id,
        "telegram_username": user.telegram_username,
        "language": user.language,
        "timezone": user.timezone,
        "account_status": user.account_status,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "subscription": {
            "plan": user.subscription.plan if user.subscription else None,
            "active": user.subscription.active if user.subscription else False,
            "start_date": user.subscription.start_date.isoformat() if user.subscription and user.subscription.start_date else None,
            "end_date": user.subscription.end_date.isoformat() if user.subscription and user.subscription.end_date else None,
        } if user.subscription else None,
        "licenses": [
            {"id": l.id, "license_key": l.license_key, "plan": l.plan, "status": l.status, "expires_at": l.expires_at.isoformat() if l.expires_at else None}
            for l in (user.licenses or [])
        ],
        "accounts": [
            {"id": a.id, "broker": a.broker, "platform": a.platform, "login": a.login,
             "account_type": a.account_type, "active": a.active, "engine_status": a.engine_status}
            for a in (user.accounts or [])
        ],
    }

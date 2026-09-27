from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import get_session
from database.models import PlanDefinition, Promotion
from security.auth import Permission, get_current_admin_user, log_event, require_permission

router = APIRouter(tags=["admin", "promotions"])


def _parse_dt(val):
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    try:
        return datetime.fromisoformat(val.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _promo_to_dict(p: Promotion) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "plan_id": p.plan_id,
        "old_price": p.old_price,
        "new_price": p.new_price,
        "discount_percent": p.discount_percent,
        "badge_text": p.badge_text,
        "start_date": p.start_date.isoformat() if p.start_date else None,
        "end_date": p.end_date.isoformat() if p.end_date else None,
        "active": p.active,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


@router.get("/promotions")
async def list_promotions(
    plan_id: str = None,
    active: bool = None,
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    _=Depends(get_current_admin_user),
):
    now = datetime.now(timezone.utc)

    # Auto-deactivate expired promotions
    expired = await session.execute(
        select(Promotion).where(
            Promotion.active == True,
            Promotion.end_date != None,
            Promotion.end_date < now,
        )
    )
    for p in expired.scalars().all():
        p.active = False
    if expired.scalars().all():
        await session.flush()

    query = select(Promotion).order_by(Promotion.created_at.desc())
    count_query = select(func.count()).select_from(Promotion)
    if plan_id:
        query = query.where(Promotion.plan_id == plan_id)
        count_query = count_query.where(Promotion.plan_id == plan_id)
    if active is not None:
        query = query.where(Promotion.active == active)
        count_query = count_query.where(Promotion.active == active)
    total = (await session.execute(count_query)).scalar() or 0
    query = query.offset(offset).limit(limit)
    result = await session.execute(query)
    return {"items": [_promo_to_dict(p) for p in result.scalars().all()], "total": total}


@router.post("/promotions")
async def create_promotion(
    body: dict,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission(Permission.SUBSCRIPTIONS_UPDATE)),
):
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name required")
    plan_id = body.get("plan_id")
    if not plan_id:
        raise HTTPException(status_code=400, detail="plan_id required")
    plan_check = await session.execute(select(PlanDefinition).where(PlanDefinition.id == plan_id))
    if not plan_check.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Plan not found")

    old_price = body.get("old_price", 0)
    new_price = body.get("new_price", 0)
    discount = 0
    if old_price and old_price > new_price:
        discount = round((1 - new_price / old_price) * 100)

    promo = Promotion(
        name=name,
        plan_id=plan_id,
        old_price=float(old_price),
        new_price=float(new_price),
        discount_percent=body.get("discount_percent", discount),
        badge_text=body.get("badge_text"),
        start_date=_parse_dt(body.get("start_date")),
        end_date=_parse_dt(body.get("end_date")),
        active=body.get("active", True),
    )
    session.add(promo)
    await session.flush()
    audit_id = await log_event(session, "promotion.created", f"Promotion '{name}' created",
                                user_id=current_user.id, payload={"promo_id": promo.id})
    await session.commit()
    return {"id": promo.id, "audit_id": audit_id, "message": "Promotion created"}


@router.put("/promotions/{promo_id}")
async def update_promotion(
    promo_id: str,
    body: dict,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission(Permission.SUBSCRIPTIONS_UPDATE)),
):
    result = await session.execute(select(Promotion).where(Promotion.id == promo_id))
    promo = result.scalar_one_or_none()
    if not promo:
        raise HTTPException(status_code=404, detail="Promotion not found")

    if "name" in body:
        promo.name = body["name"]
    if "plan_id" in body:
        plan_check = await session.execute(select(PlanDefinition).where(PlanDefinition.id == body["plan_id"]))
        if not plan_check.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Plan not found")
        promo.plan_id = body["plan_id"]
    if "old_price" in body:
        promo.old_price = float(body["old_price"])
    if "new_price" in body:
        promo.new_price = float(body["new_price"])
    if "discount_percent" in body:
        promo.discount_percent = int(body["discount_percent"])
    else:
        # Auto-calculate discount
        old = body.get("old_price", promo.old_price)
        new = body.get("new_price", promo.new_price)
        if old and new and old > new:
            promo.discount_percent = round((1 - new / old) * 100)
    if "badge_text" in body:
        promo.badge_text = body["badge_text"]
    if "start_date" in body:
        promo.start_date = _parse_dt(body["start_date"])
    if "end_date" in body:
        promo.end_date = _parse_dt(body["end_date"])
    if "active" in body:
        promo.active = bool(body["active"])

    audit_id = await log_event(session, "promotion.updated", f"Promotion '{promo.name}' updated",
                                user_id=current_user.id)
    await session.commit()
    await session.refresh(promo)
    return {"success": True, "promotion": _promo_to_dict(promo), "audit_id": audit_id}


@router.delete("/promotions/{promo_id}")
async def delete_promotion(
    promo_id: str,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission(Permission.SUBSCRIPTIONS_UPDATE)),
):
    result = await session.execute(select(Promotion).where(Promotion.id == promo_id))
    promo = result.scalar_one_or_none()
    if not promo:
        raise HTTPException(status_code=404, detail="Promotion not found")
    await session.delete(promo)
    audit_id = await log_event(session, "promotion.deleted", f"Promotion '{promo.name}' deleted",
                                user_id=current_user.id)
    await session.commit()
    return {"success": True, "audit_id": audit_id, "message": "Promotion deleted"}


@router.post("/promotions/{promo_id}/toggle")
async def toggle_promotion(
    promo_id: str,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission(Permission.SUBSCRIPTIONS_UPDATE)),
):
    result = await session.execute(select(Promotion).where(Promotion.id == promo_id))
    promo = result.scalar_one_or_none()
    if not promo:
        raise HTTPException(status_code=404, detail="Promotion not found")
    promo.active = not promo.active
    audit_id = await log_event(session, "promotion.toggled", f"Promotion '{promo.name}' {'activated' if promo.active else 'deactivated'}",
                                user_id=current_user.id)
    await session.commit()
    return {"success": True, "active": promo.active, "audit_id": audit_id}

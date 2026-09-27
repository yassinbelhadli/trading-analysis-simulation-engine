"""Coupon management routes."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import get_session
from database.models import Coupon, CouponRedemption, PlanDefinition
from security.auth import Permission, get_current_user, log_event, require_permission

from api.services.coupon_service import (
    VALID_CURRENCIES,
    CouponValidationError,
    validate_coupon_for_purchase,
)

router = APIRouter(prefix="/coupons", tags=["coupons"])

# Uppercase alphanumeric + underscores/hyphens (must contain at least one letter/digit)
_CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9_-]{2,49}$")


def _parse_dt(val):
    """Parse an ISO datetime from JSON; None-safe."""
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    try:
        return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail=f"Invalid datetime value: {val!r}")


def _parse_decimal(value, field: str) -> Decimal:
    if value is None or value == "":
        raise HTTPException(status_code=400, detail=f"{field} is required")
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise HTTPException(status_code=400, detail=f"{field} must be a valid number")
    if d < 0:
        raise HTTPException(status_code=400, detail=f"{field} cannot be negative")
    return d


def _coupon_to_dict(c: Coupon) -> dict:
    return {
        "id": c.id,
        "code": c.code,
        "name": c.name,
        "description": c.description,
        "discount_type": c.discount_type,
        "discount_value": float(c.discount_value) if c.discount_value is not None else None,
        "currency": c.currency,
        "valid_from": c.valid_from.isoformat() if c.valid_from else None,
        "valid_until": c.valid_until.isoformat() if c.valid_until else None,
        "max_redemptions": c.max_redemptions,
        "max_per_user": c.max_per_user,
        "min_subscription_value": float(c.min_subscription_value) if c.min_subscription_value is not None else None,
        "applicable_plans": c.applicable_plans,
        "active": c.active,
        "total_redemptions": c.total_redemptions,
        "total_discount_granted": float(c.total_discount_granted) if c.total_discount_granted is not None else 0.0,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


async def _get_coupon_or_404(session: AsyncSession, coupon_id: str) -> Coupon:
    result = await session.execute(select(Coupon).where(Coupon.id == coupon_id))
    coupon = result.scalar_one_or_none()
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")
    return coupon


async def _ensure_code_unique(session: AsyncSession, code: str, exclude_id: str | None = None) -> None:
    query = select(Coupon).where(Coupon.code == code)
    if exclude_id:
        query = query.where(Coupon.id != exclude_id)
    result = await session.execute(query)
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Coupon code '{code}' already exists")


# ---------------------------------------------------------------------------
# GET /coupons — list all coupons with stats
# ---------------------------------------------------------------------------
@router.get("")
async def list_coupons(
    current_user=Depends(require_permission(Permission.COUPONS_READ)),
    session: AsyncSession = Depends(get_session),
):
    """List all coupons ordered by creation date (newest first)."""
    result = await session.execute(select(Coupon).order_by(Coupon.created_at.desc()))
    coupons = result.scalars().all()
    return {"items": [_coupon_to_dict(c) for c in coupons], "total": len(coupons)}


# ---------------------------------------------------------------------------
# POST /coupons — create coupon
# ---------------------------------------------------------------------------
@router.post("")
async def create_coupon(
    body: dict,
    current_user=Depends(require_permission(Permission.COUPONS_CREATE)),
    session: AsyncSession = Depends(get_session),
):
    """Create a new discount coupon."""
    code = str(body.get("code") or "").strip().upper()
    name = str(body.get("name") or "").strip()

    if not code:
        raise HTTPException(status_code=400, detail="code is required")
    if not _CODE_RE.match(code):
        raise HTTPException(
            status_code=400,
            detail="code must be 3-50 characters: uppercase letters, digits, '_' or '-'",
        )
    await _ensure_code_unique(session, code)

    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    discount_type = str(body.get("discount_type") or "").strip().lower()
    if discount_type not in ("percentage", "fixed_amount"):
        raise HTTPException(status_code=400, detail='discount_type must be "percentage" or "fixed_amount"')

    discount_value = _parse_decimal(body.get("discount_value"), "discount_value")
    if discount_value <= 0:
        raise HTTPException(status_code=400, detail="discount_value must be greater than 0")

    currency = None
    if discount_type == "percentage":
        if discount_value > 100:
            raise HTTPException(status_code=400, detail="Percentage discount must be between 0 and 100")
    else:  # fixed_amount
        currency = str(body.get("currency") or "").strip().upper()
        if not currency:
            raise HTTPException(status_code=400, detail="currency is required for fixed_amount coupons")
        if currency not in VALID_CURRENCIES:
            raise HTTPException(status_code=400, detail=f"currency must be one of: {', '.join(sorted(VALID_CURRENCIES))}")

    # Validate applicable plans exist
    applicable_plans = body.get("applicable_plans")
    if applicable_plans is not None:
        if not isinstance(applicable_plans, list):
            raise HTTPException(status_code=400, detail="applicable_plans must be a list of plan ids")
        for pid in applicable_plans:
            result = await session.execute(select(PlanDefinition).where(PlanDefinition.id == pid))
            if not result.scalar_one_or_none():
                raise HTTPException(status_code=404, detail=f"Plan '{pid}' not found")

    max_redemptions = body.get("max_redemptions")
    if max_redemptions is not None:
        try:
            max_redemptions = int(max_redemptions)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="max_redemptions must be an integer")
        if max_redemptions <= 0:
            raise HTTPException(status_code=400, detail="max_redemptions must be greater than 0")

    max_per_user = body.get("max_per_user", 1)
    try:
        max_per_user = int(max_per_user)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="max_per_user must be an integer")
    if max_per_user <= 0:
        raise HTTPException(status_code=400, detail="max_per_user must be greater than 0")

    min_subscription_value = None
    if body.get("min_subscription_value") is not None:
        min_subscription_value = _parse_decimal(body.get("min_subscription_value"), "min_subscription_value")

    valid_from = _parse_dt(body.get("valid_from"))
    valid_until = _parse_dt(body.get("valid_until"))
    if valid_from and valid_until and valid_from > valid_until:
        raise HTTPException(status_code=400, detail="valid_from must be before valid_until")

    coupon = Coupon(
        code=code,
        name=name,
        description=body.get("description"),
        discount_type=discount_type,
        discount_value=discount_value,
        currency=currency,
        valid_from=valid_from,
        valid_until=valid_until,
        max_redemptions=max_redemptions,
        max_per_user=max_per_user,
        min_subscription_value=min_subscription_value,
        applicable_plans=applicable_plans,
        active=bool(body.get("active", True)),
    )
    session.add(coupon)
    await log_event(session, "coupon.created", f"Coupon '{code}' created",
                    user_id=current_user.id, payload={"code": code, "discount_type": discount_type})
    await session.commit()
    await session.refresh(coupon)
    return {"success": True, "coupon": _coupon_to_dict(coupon)}


# ---------------------------------------------------------------------------
# PUT /coupons/{coupon_id} — partial update
# ---------------------------------------------------------------------------
@router.put("/{coupon_id}")
async def update_coupon(
    coupon_id: str,
    body: dict,
    current_user=Depends(require_permission(Permission.COUPONS_UPDATE)),
    session: AsyncSession = Depends(get_session),
):
    """Partially update a coupon."""
    coupon = await _get_coupon_or_404(session, coupon_id)

    if "code" in body:
        code = str(body["code"] or "").strip().upper()
        if not code:
            raise HTTPException(status_code=400, detail="code cannot be empty")
        if not _CODE_RE.match(code):
            raise HTTPException(
                status_code=400,
                detail="code must be 3-50 characters: uppercase letters, digits, '_' or '-'",
            )
        if code != coupon.code:
            await _ensure_code_unique(session, code, exclude_id=coupon.id)
        coupon.code = code

    if "name" in body:
        if not str(body["name"] or "").strip():
            raise HTTPException(status_code=400, detail="name cannot be empty")
        coupon.name = str(body["name"]).strip()

    if "description" in body:
        coupon.description = body["description"]

    if "discount_type" in body:
        discount_type = str(body["discount_type"] or "").strip().lower()
        if discount_type not in ("percentage", "fixed_amount"):
            raise HTTPException(status_code=400, detail='discount_type must be "percentage" or "fixed_amount"')
        coupon.discount_type = discount_type

    if "discount_value" in body:
        discount_value = _parse_decimal(body["discount_value"], "discount_value")
        if discount_value <= 0:
            raise HTTPException(status_code=400, detail="discount_value must be greater than 0")
        coupon.discount_value = discount_value

    # Re-validate the percentage/fixed_amount rules after any change to either field
    effective_type = coupon.discount_type
    effective_value = coupon.discount_value
    if effective_type == "percentage":
        if effective_value is not None and effective_value > 100:
            raise HTTPException(status_code=400, detail="Percentage discount must be between 0 and 100")
        coupon.currency = None
    elif effective_type == "fixed_amount":
        if "currency" in body:
            currency = str(body["currency"] or "").strip().upper() or None
        elif not coupon.currency:
            currency = None
        else:
            currency = coupon.currency
        if not currency:
            raise HTTPException(status_code=400, detail="currency is required for fixed_amount coupons")
        if currency not in VALID_CURRENCIES:
            raise HTTPException(status_code=400, detail=f"currency must be one of: {', '.join(sorted(VALID_CURRENCIES))}")
        coupon.currency = currency

    if "valid_from" in body:
        coupon.valid_from = _parse_dt(body["valid_from"])
    if "valid_until" in body:
        coupon.valid_until = _parse_dt(body["valid_until"])
    if coupon.valid_from and coupon.valid_until and coupon.valid_from > coupon.valid_until:
        raise HTTPException(status_code=400, detail="valid_from must be before valid_until")

    if "max_redemptions" in body:
        raw = body["max_redemptions"]
        if raw is None:
            coupon.max_redemptions = None
        else:
            try:
                mr = int(raw)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail="max_redemptions must be an integer")
            if mr <= 0:
                raise HTTPException(status_code=400, detail="max_redemptions must be greater than 0")
            coupon.max_redemptions = mr

    if "max_per_user" in body:
        try:
            mpu = int(body["max_per_user"])
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="max_per_user must be an integer")
        if mpu <= 0:
            raise HTTPException(status_code=400, detail="max_per_user must be greater than 0")
        coupon.max_per_user = mpu

    if "min_subscription_value" in body:
        coupon.min_subscription_value = (
            _parse_decimal(body["min_subscription_value"], "min_subscription_value")
            if body["min_subscription_value"] is not None
            else None
        )

    if "applicable_plans" in body:
        plans = body["applicable_plans"]
        if plans is not None:
            if not isinstance(plans, list):
                raise HTTPException(status_code=400, detail="applicable_plans must be a list of plan ids")
            for pid in plans:
                result = await session.execute(select(PlanDefinition).where(PlanDefinition.id == pid))
                if not result.scalar_one_or_none():
                    raise HTTPException(status_code=404, detail=f"Plan '{pid}' not found")
        coupon.applicable_plans = plans

    if "active" in body:
        coupon.active = bool(body["active"])

    await log_event(session, "coupon.updated", f"Coupon '{coupon.code}' updated",
                    user_id=current_user.id, payload={"changes": list(body.keys())})
    await session.commit()
    await session.refresh(coupon)
    return {"success": True, "coupon": _coupon_to_dict(coupon)}


# ---------------------------------------------------------------------------
# POST /coupons/{coupon_id}/toggle — toggle active status
# ---------------------------------------------------------------------------
@router.post("/{coupon_id}/toggle")
async def toggle_coupon(
    coupon_id: str,
    current_user=Depends(require_permission(Permission.COUPONS_UPDATE)),
    session: AsyncSession = Depends(get_session),
):
    """Toggle a coupon's active status."""
    coupon = await _get_coupon_or_404(session, coupon_id)
    coupon.active = not coupon.active
    await log_event(session, "coupon.toggled",
                    f"Coupon '{coupon.code}' {'activated' if coupon.active else 'deactivated'}",
                    user_id=current_user.id)
    await session.commit()
    return {"success": True, "id": coupon.id, "code": coupon.code, "active": coupon.active}


# ---------------------------------------------------------------------------
# DELETE /coupons/{coupon_id} — soft delete (active=False)
# ---------------------------------------------------------------------------
@router.delete("/{coupon_id}")
async def delete_coupon(
    coupon_id: str,
    current_user=Depends(require_permission(Permission.COUPONS_DELETE)),
    session: AsyncSession = Depends(get_session),
):
    """Soft-delete a coupon by deactivating it. Redemption history is preserved."""
    coupon = await _get_coupon_or_404(session, coupon_id)
    coupon.active = False
    await log_event(session, "coupon.deleted", f"Coupon '{coupon.code}' deactivated (soft-deleted)",
                    user_id=current_user.id)
    await session.commit()
    return {"success": True, "message": f"Coupon '{coupon.code}' deactivated", "id": coupon.id}


# ---------------------------------------------------------------------------
# POST /coupons/validate — validate coupon for purchase preview
# ---------------------------------------------------------------------------
@router.post("/validate")
async def validate_coupon(
    body: dict,
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Validate a coupon against a plan/currency and preview the discount.

    Body: ``{code, plan_id, currency}``
    """
    code = str(body.get("code") or "").strip().upper()
    plan_id = str(body.get("plan_id") or "").strip()
    currency = str(body.get("currency") or "").strip().upper()

    if not code:
        raise HTTPException(status_code=400, detail="code is required")
    if not plan_id:
        raise HTTPException(status_code=400, detail="plan_id is required")

    result = await session.execute(select(PlanDefinition).where(PlanDefinition.id == plan_id))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    try:
        coupon, original_price, discount_amount, final_price = await validate_coupon_for_purchase(
            session, code=code, user_id=current_user.id, plan=plan, currency=currency,
        )
    except CouponValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)

    return {
        "valid": True,
        "coupon_code": coupon.code,
        "original_price": float(original_price),
        "discount_amount": float(discount_amount),
        "final_price": float(final_price),
        "message": f"Coupon '{coupon.code}' applied",
    }

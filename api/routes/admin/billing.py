from __future__ import annotations

import random
import string
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pathlib import Path
from sqlalchemy import Float, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.plans_config import PLANS as DEFAULT_PLANS
from api.services.coupon_service import (
    VALID_CURRENCIES,
    CouponValidationError,
    generate_subscription_number,
    get_plan_price,
    validate_coupon_for_purchase,
)
from database.db import get_session
from database.models import AuditLog, CouponRedemption, License, Payment, PlanDefinition, Promotion, Subscription, TradingAccount, User
from security.auth import Permission, get_current_admin_user, log_event, require_permission, require_role

router = APIRouter(tags=["admin", "billing"])

VALID_CURRENCIES = {"USD", "EUR", "MAD"}

# Proof-of-payment files uploaded by clients (same storage as the client route)
PROOF_STORAGE_DIR = Path(__file__).resolve().parents[3] / "storage" / "uploads" / "proofs"


# ---------------------------------------------------------------------------
# GET /uploads/proofs/{filename} — owner/admin views a client's proof file
# ---------------------------------------------------------------------------
@router.get("/uploads/proofs/{filename}")
async def admin_serve_payment_proof(
    filename: str,
    _=Depends(require_permission(Permission.PAYMENTS_READ)),
):
    """Serve an uploaded proof file to an owner/admin with PAYMENTS_READ."""
    safe = Path(filename).name
    if safe != filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    file_path = PROOF_STORAGE_DIR / safe
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Proof file not found")
    ext = f".{safe.lower().rsplit('.', 1)[-1]}"
    media_type = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }.get(ext, "application/octet-stream")
    return FileResponse(path=file_path, media_type=media_type)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _to_decimal(value) -> Decimal | None:
    """Convert an incoming JSON value to Decimal for money math (never float)."""
    if value is None or value == "":
        return None
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise HTTPException(status_code=400, detail=f"Invalid numeric value: {value!r}")
    if d < 0:
        raise HTTPException(status_code=400, detail="Price values cannot be negative")
    return d


def _dec_out(value) -> float | None:
    """Serialize a Decimal money value for JSON output."""
    return float(value) if value is not None else None


def _plan_to_dict(p: PlanDefinition) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "price_monthly": p.price_monthly,
        "price_yearly": p.price_yearly,
        "one_time_price": p.one_time_price,
        "price_usd": _dec_out(p.price_usd),
        "price_eur": _dec_out(p.price_eur),
        "price_mad": _dec_out(p.price_mad),
        "duration_days": p.duration_days,
        "max_accounts": p.max_accounts,
        "max_daily_loss": p.max_daily_loss,
        "max_risk_per_trade": p.max_risk_per_trade,
        "features": p.features or {},
        "features_json": p.features_json or p.features or {},
        "description": p.description,
        "badge": p.badge,
        "display_order": p.display_order,
        "on_sale": p.on_sale,
        "old_price": p.old_price,
        "sale_label": p.sale_label,
        "sort_order": p.sort_order,
        "is_archived": p.is_archived,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def _apply_plan_pricing_fields(plan: PlanDefinition, body: dict) -> None:
    """Apply multi-currency pricing / metadata fields from a request body.

    Shared by create and update so validation stays identical.
    """
    for field in ("price_usd", "price_eur", "price_mad"):
        if field in body:
            setattr(plan, field, _to_decimal(body[field]))

    if "duration_days" in body:
        raw = body["duration_days"]
        if raw is not None:
            try:
                duration = int(raw)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail="duration_days must be a positive integer")
            if duration <= 0:
                raise HTTPException(status_code=400, detail="duration_days must be greater than 0")
            plan.duration_days = duration

    if "features_json" in body:
        if body["features_json"] is not None and not isinstance(body["features_json"], dict):
            raise HTTPException(status_code=400, detail="features_json must be an object")
        plan.features_json = body["features_json"] or {}

    if "description" in body:
        plan.description = body["description"]
    if "badge" in body:
        badge = body["badge"]
        if badge is not None and len(str(badge)) > 100:
            raise HTTPException(status_code=400, detail="badge must be 100 characters or fewer")
        plan.badge = badge
    if "display_order" in body:
        try:
            plan.display_order = int(body["display_order"])
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="display_order must be an integer")


async def _seed_plans_if_empty(session: AsyncSession):
    """Populate plan_definitions table from default config if empty."""
    result = await session.execute(select(func.count()).select_from(PlanDefinition))
    if result.scalar() > 0:
        return
    for i, (pid, cfg) in enumerate(DEFAULT_PLANS.items()):
        p = PlanDefinition(
            id=pid,
            name=cfg["name"],
            price_monthly=cfg.get("price_monthly"),
            price_yearly=cfg.get("price_yearly"),
            one_time_price=cfg.get("one_time_price"),
            max_accounts=cfg.get("max_accounts", 1),
            max_daily_loss=cfg.get("max_daily_loss", 500),
            max_risk_per_trade=cfg.get("max_risk_per_trade", 0.5),
            features=cfg.get("features", {}),
            on_sale=cfg.get("on_sale", False),
            old_price=cfg.get("old_price"),
            sale_label=cfg.get("sale_label"),
            sort_order=i,
        )
        session.add(p)
    await session.commit()


# ---------------------------------------------------------------------------
# Available plans (DB-backed, fallback to config)
# Admin+owner only — clients must use GET /api/client/subscription.
# ---------------------------------------------------------------------------
@router.get("/plans")
async def list_plans(
    session: AsyncSession = Depends(get_session),
    _=Depends(get_current_admin_user),
):
    await _seed_plans_if_empty(session)
    result = await session.execute(
        select(PlanDefinition)
        .where(PlanDefinition.is_archived == False)
        .order_by(PlanDefinition.sort_order)
    )
    plans = result.scalars().all()

    # Fetch active promotions and group by plan_id
    now = datetime.now(timezone.utc)
    promo_result = await session.execute(
        select(Promotion).where(
            Promotion.active == True,
            Promotion.start_date <= now,
            Promotion.end_date >= now,
        )
    )
    active_promos = {}
    for p in promo_result.scalars().all():
        active_promos[p.plan_id] = {
            "id": p.id,
            "name": p.name,
            "old_price": p.old_price,
            "new_price": p.new_price,
            "discount_percent": p.discount_percent,
            "badge_text": p.badge_text,
            "end_date": p.end_date.isoformat() if p.end_date else None,
        }

    if plans:
        # Active-subscriber counts per plan (single grouped query, no N+1)
        counts_result = await session.execute(
            select(Subscription.plan, func.count().label("cnt"))
            .where(Subscription.active == True)
            .group_by(Subscription.plan)
        )
        subscriber_counts = {row.plan: row.cnt for row in counts_result.all()}

        items = [_plan_to_dict(p) for p in plans]
        for item in items:
            item["subscriber_count"] = subscriber_counts.get(item["id"], 0)
            promo = active_promos.get(item["id"])
            if promo:
                item["promotion"] = promo
        return {"items": items}
    return {"items": [{"id": k, **v} for k, v in DEFAULT_PLANS.items()]}


# ---------------------------------------------------------------------------
# Get single plan (includes archived — used by management UI to un-archive)
# ---------------------------------------------------------------------------
@router.get("/plans/{plan_id}")
async def get_plan(
    plan_id: str,
    session: AsyncSession = Depends(get_session),
    _=Depends(get_current_admin_user),
):
    result = await session.execute(select(PlanDefinition).where(PlanDefinition.id == plan_id))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return {"plan": _plan_to_dict(plan)}


# ---------------------------------------------------------------------------
# Create plan
# ---------------------------------------------------------------------------
@router.post("/plans")
async def create_plan(
    body: dict,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission(Permission.SUBSCRIPTIONS_CREATE)),
):
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    plan_id = (body.get("id") or "").strip() or None
    if plan_id:
        if not plan_id.replace("_", "").replace("-", "").isalnum():
            raise HTTPException(status_code=400, detail="id may only contain letters, digits, '_' and '-'")
    else:
        plan_id = name.lower().replace(" ", "-").replace("_", "-")

    result = await session.execute(select(PlanDefinition).where(PlanDefinition.id == plan_id))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Plan '{plan_id}' already exists")

    # At least one multi-currency price must be provided
    if not any(body.get(f) for f in ("price_usd", "price_eur", "price_mad")):
        raise HTTPException(status_code=400, detail="At least one price is required (price_usd, price_eur or price_mad)")

    plan = PlanDefinition(
        id=plan_id,
        name=name,
        price_monthly=body.get("price_monthly"),
        price_yearly=body.get("price_yearly"),
        one_time_price=body.get("one_time_price"),
        max_accounts=int(body.get("max_accounts", 1)),
        max_daily_loss=float(body.get("max_daily_loss", 500)),
        max_risk_per_trade=float(body.get("max_risk_per_trade", 0.5)),
        features=body.get("features") or {},
        on_sale=bool(body.get("on_sale", False)),
        old_price=body.get("old_price"),
        sale_label=body.get("sale_label"),
        sort_order=int(body.get("sort_order", 0)),
    )
    _apply_plan_pricing_fields(plan, body)
    session.add(plan)
    await log_event(session, "plan.created", f"Plan '{plan_id}' created",
                    user_id=current_user.id, payload={"name": name})
    await session.commit()
    await session.refresh(plan)
    return {"success": True, "plan": _plan_to_dict(plan)}


# ---------------------------------------------------------------------------
# Delete plan — SAFE ARCHIVE (soft-delete): keeps the row so existing
# subscriptions and promotion FKs stay valid; the plan is hidden from
# listings and blocked for new subscriptions.
# ---------------------------------------------------------------------------
@router.delete("/plans/{plan_id}")
async def archive_plan(
    plan_id: str,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission(Permission.SUBSCRIPTIONS_UPDATE)),
):
    result = await session.execute(select(PlanDefinition).where(PlanDefinition.id == plan_id))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan.is_archived = True
    await log_event(session, "plan.archived", f"Plan '{plan_id}' archived (soft-deleted)",
                    user_id=current_user.id)
    await session.commit()
    return {"success": True, "message": f"Plan '{plan_id}' archived", "plan": _plan_to_dict(plan)}


# ---------------------------------------------------------------------------
# Update plan
# ---------------------------------------------------------------------------
@router.put("/plans/{plan_id}")
async def update_plan(
    plan_id: str,
    body: dict,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission(Permission.SUBSCRIPTIONS_UPDATE)),
):
    result = await session.execute(select(PlanDefinition).where(PlanDefinition.id == plan_id))
    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    if "name" in body:
        plan.name = body["name"]
    if "price_monthly" in body:
        plan.price_monthly = body["price_monthly"]
    if "price_yearly" in body:
        plan.price_yearly = body["price_yearly"]
    if "one_time_price" in body:
        plan.one_time_price = body["one_time_price"]
    if "max_accounts" in body:
        plan.max_accounts = int(body["max_accounts"])
    if "max_daily_loss" in body:
        plan.max_daily_loss = float(body["max_daily_loss"])
    if "max_risk_per_trade" in body:
        plan.max_risk_per_trade = float(body["max_risk_per_trade"])
    if "features" in body:
        plan.features = body["features"]
    if "on_sale" in body:
        plan.on_sale = bool(body["on_sale"])
    if "old_price" in body:
        plan.old_price = body["old_price"]
    if "sale_label" in body:
        plan.sale_label = body["sale_label"]
    if "sort_order" in body:
        plan.sort_order = int(body["sort_order"])
    if "is_archived" in body:
        plan.is_archived = bool(body["is_archived"])
    _apply_plan_pricing_fields(plan, body)

    await log_event(session, "plan.updated", f"Plan {plan_id} updated",
                    user_id=current_user.id, payload={"changes": body})
    await session.commit()
    await session.refresh(plan)
    return {"success": True, "plan": _plan_to_dict(plan)}


# ---------------------------------------------------------------------------
# Restore default plans (reset built-ins to config values, archive custom ones)
# Never hard-deletes: preserves subscription history and promotion FKs.
# ---------------------------------------------------------------------------
@router.post("/plans/restore-defaults")
async def restore_default_plans(
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission(Permission.SUBSCRIPTIONS_UPDATE)),
):
    for i, (pid, cfg) in enumerate(DEFAULT_PLANS.items()):
        result = await session.execute(select(PlanDefinition).where(PlanDefinition.id == pid))
        p = result.scalar_one_or_none()
        if p is None:
            p = PlanDefinition(id=pid, name=cfg["name"])
            session.add(p)
        p.name = cfg["name"]
        p.price_monthly = cfg.get("price_monthly")
        p.price_yearly = cfg.get("price_yearly")
        p.one_time_price = cfg.get("one_time_price")
        p.max_accounts = cfg.get("max_accounts", 1)
        p.max_daily_loss = cfg.get("max_daily_loss", 500)
        p.max_risk_per_trade = cfg.get("max_risk_per_trade", 0.5)
        p.features = cfg.get("features", {})
        p.on_sale = cfg.get("on_sale", False)
        p.old_price = cfg.get("old_price")
        p.sale_label = cfg.get("sale_label")
        p.sort_order = i
        p.is_archived = False

    # Soft-archive any plan that is not part of the defaults (data preserved)
    result = await session.execute(select(PlanDefinition))
    for p in result.scalars().all():
        if p.id not in DEFAULT_PLANS:
            p.is_archived = True

    await log_event(session, "plans.restored", "Plans restored to defaults (custom plans archived)",
                    user_id=current_user.id)
    await session.commit()

    result = await session.execute(
        select(PlanDefinition)
        .where(PlanDefinition.is_archived == False)
        .order_by(PlanDefinition.sort_order)
    )
    return {"success": True, "items": [_plan_to_dict(p) for p in result.scalars().all()]}


# ---------------------------------------------------------------------------
# Subscriptions list  (admin+owner only — client role must not read global data)
# ---------------------------------------------------------------------------
@router.get("/subscriptions")
async def list_subscriptions(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    _=Depends(get_current_admin_user),
):
    query = select(Subscription).order_by(Subscription.start_date.desc()).offset(offset).limit(limit)
    count_query = select(func.count()).select_from(Subscription)
    total = (await session.execute(count_query)).scalar() or 0
    result = await session.execute(query)
    subs = result.scalars().all()
    return {
        "items": [
            {
                "id": s.id,
                "subscription_number": s.subscription_number,
                "user_id": s.user_id,
                "plan": s.plan,
                "plan_name": s.plan_name,
                "billing_cycle": s.billing_cycle,
                "price": s.price,
                "plan_price_paid": float(s.plan_price_paid) if s.plan_price_paid is not None else None,
                "plan_currency": s.plan_currency,
                "coupon_code": s.coupon_code,
                "discount_amount": float(s.discount_amount) if s.discount_amount is not None else None,
                "start_date": s.start_date.isoformat() if s.start_date else None,
                "end_date": s.end_date.isoformat() if s.end_date else None,
                "active": s.active,
            }
            for s in subs
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


# ---------------------------------------------------------------------------
# Create subscription (with multi-currency pricing + optional coupon)
# ---------------------------------------------------------------------------
@router.post("/subscriptions/create")
async def create_subscription(
    body: dict,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission(Permission.SUBSCRIPTIONS_CREATE)),
):
    """Create a subscription for a user with a currency price snapshot.

    Body: ``{user_id, plan_id, currency, coupon_code?}``
    """
    user_id = str(body.get("user_id") or "").strip()
    plan_id = str(body.get("plan_id") or "").strip()
    currency = str(body.get("currency") or "").strip().upper()
    coupon_code = str(body.get("coupon_code") or "").strip().upper() or None

    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    if not plan_id:
        raise HTTPException(status_code=400, detail="plan_id is required")

    user_result = await session.execute(select(User).where(User.id == user_id))
    target_user = user_result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    # A user holds at most one subscription row (unique user_id)
    existing_result = await session.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    )
    if existing_result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="User already has a subscription")

    plan_result = await session.execute(select(PlanDefinition).where(PlanDefinition.id == plan_id))
    plan = plan_result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if plan.is_archived:
        raise HTTPException(status_code=400, detail="Plan is archived and cannot be subscribed to")

    if currency not in VALID_CURRENCIES:
        raise HTTPException(status_code=400, detail=f"currency must be one of: {', '.join(sorted(VALID_CURRENCIES))}")

    original_price = await get_plan_price(plan, currency)
    if original_price is None:
        raise HTTPException(status_code=400, detail=f"Plan '{plan.id}' has no price configured for {currency}")

    discount_amount = Decimal("0")
    applied_coupon_code = None
    if coupon_code:
        try:
            coupon, original_price, discount_amount, _final = await validate_coupon_for_purchase(
                session, code=coupon_code, user_id=user_id, plan=plan, currency=currency,
            )
            applied_coupon_code = coupon.code
        except CouponValidationError as exc:
            raise HTTPException(status_code=exc.status_code, detail=f"Coupon error: {exc.message}")

    final_price = max(Decimal("0"), original_price - discount_amount)

    now = datetime.now(timezone.utc)
    duration_days = plan.duration_days or 30
    features_snapshot = plan.features_json or plan.features or {}

    sub = Subscription(
        user_id=user_id,
        plan=str(plan.id),
        plan_name=plan.name,
        plan_description=plan.description,
        plan_duration_days=duration_days,
        plan_price_paid=final_price,
        plan_currency=currency,
        plan_features=features_snapshot,
        coupon_code=applied_coupon_code,
        discount_amount=discount_amount,
        start_date=now,
        end_date=now + timedelta(days=duration_days),
        active=True,
        billing_cycle="one_time",
        subscription_number=generate_subscription_number(),
        price=float(final_price),
    )
    session.add(sub)
    await session.flush()

    # Record the redemption audit trail and update denormalized stats
    if applied_coupon_code:
        session.add(CouponRedemption(
            coupon_id=coupon.id,
            user_id=user_id,
            subscription_id=sub.id,
            original_price=original_price,
            discount_amount=discount_amount,
            final_price=final_price,
            currency=currency,
        ))
        coupon.total_redemptions += 1
        coupon.total_discount_granted = (coupon.total_discount_granted or Decimal("0")) + discount_amount

    await log_event(session, "subscription.created",
                    f"Subscription {sub.subscription_number} created for user {user_id}",
                    user_id=current_user.id,
                    payload={
                        "subscription_id": sub.id,
                        "target_user_id": user_id,
                        "plan_id": plan.id,
                        "currency": currency,
                        "original_price": float(original_price),
                        "discount_amount": float(discount_amount),
                        "final_price": float(final_price),
                        "coupon_code": applied_coupon_code,
                    })
    await session.commit()
    await session.refresh(sub)

    return {
        "success": True,
        "subscription": {
            "id": sub.id,
            "subscription_number": sub.subscription_number,
            "user_id": sub.user_id,
            "plan": sub.plan,
            "plan_name": sub.plan_name,
            "plan_description": sub.plan_description,
            "plan_duration_days": sub.plan_duration_days,
            "plan_price_paid": float(sub.plan_price_paid) if sub.plan_price_paid is not None else None,
            "plan_currency": sub.plan_currency,
            "plan_features": sub.plan_features,
            "coupon_code": sub.coupon_code,
            "discount_amount": float(sub.discount_amount) if sub.discount_amount is not None else None,
            "start_date": sub.start_date.isoformat() if sub.start_date else None,
            "end_date": sub.end_date.isoformat() if sub.end_date else None,
            "active": sub.active,
            "billing_cycle": sub.billing_cycle,
        },
    }


# ---------------------------------------------------------------------------
# Update subscription
# ---------------------------------------------------------------------------
@router.patch("/subscriptions/{sub_id}")
async def update_subscription(
    sub_id: str,
    body: dict,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission(Permission.SUBSCRIPTIONS_UPDATE)),
):
    result = await session.execute(select(Subscription).where(Subscription.id == sub_id))
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    if "plan" in body:
        # Never move a subscription to an archived plan (blocked for new subs)
        if body["plan"]:
            result = await session.execute(
                select(PlanDefinition).where(PlanDefinition.id == body["plan"])
            )
            plan = result.scalar_one_or_none()
            if plan is None:
                raise HTTPException(status_code=400, detail="Unknown plan id")
            if plan.is_archived:
                raise HTTPException(status_code=400, detail="Plan is archived and cannot be assigned")
        sub.plan = body["plan"]
    if "active" in body:
        sub.active = body["active"]
    if "billing_cycle" in body:
        sub.billing_cycle = body["billing_cycle"]
    audit_id = await log_event(session, "subscription.updated", f"Subscription {sub_id} updated",
                                user_id=current_user.id, payload={"changes": body})
    await session.commit()
    return {"success": True, "audit_id": audit_id, "message": "Subscription updated"}


# ---------------------------------------------------------------------------
# Cancel subscription
# ---------------------------------------------------------------------------
@router.post("/subscriptions/{sub_id}/cancel")
async def cancel_subscription(
    sub_id: str,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission(Permission.SUBSCRIPTIONS_CANCEL)),
):
    result = await session.execute(select(Subscription).where(Subscription.id == sub_id))
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    sub.active = False
    sub.end_date = datetime.now(timezone.utc)
    audit_id = await log_event(session, "subscription.cancelled", f"Subscription {sub_id} cancelled",
                                user_id=current_user.id)
    await session.commit()
    return {"success": True, "audit_id": audit_id, "message": "Subscription cancelled"}


# ---------------------------------------------------------------------------
# Suspend subscription
# ---------------------------------------------------------------------------
@router.post("/subscriptions/{sub_id}/suspend")
async def suspend_subscription(
    sub_id: str,
    body: dict = {},
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_admin_user),
    _=Depends(require_permission(Permission.SUBSCRIPTIONS_SUSPEND)),
):
    """Suspend an active subscription. Preserves all payment history."""
    from billing.payment_service import PaymentService, PaymentServiceError
    from billing.stripe_provider import StripeProvider

    reason = body.get("reason", "")
    if not reason:
        raise HTTPException(400, "Suspension reason is required")

    svc = PaymentService(StripeProvider())
    try:
        result = await svc.suspend_subscription(
            session,
            subscription_id=sub_id,
            suspended_by=current_user.id,
            reason=reason,
        )
        await log_event(
            session, "subscription.suspended",
            f"Subscription {sub_id} suspended: {reason}",
            user_id=current_user.id,
        )
        await session.commit()
        return {"success": True, "subscription": result}
    except PaymentServiceError as e:
        raise HTTPException(e.status_code, str(e))


# ---------------------------------------------------------------------------
# Revoke subscription (owner only)
# ---------------------------------------------------------------------------
@router.post("/subscriptions/{sub_id}/revoke")
async def revoke_subscription(
    sub_id: str,
    body: dict = {},
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_admin_user),
    _=Depends(require_permission(Permission.SUBSCRIPTIONS_REVOKE)),
):
    """Permanently revoke a subscription. Owner-only. Preserves all payment history."""
    from billing.payment_service import PaymentService, PaymentServiceError
    from billing.stripe_provider import StripeProvider

    reason = body.get("reason", "")
    if not reason:
        raise HTTPException(400, "Revocation reason is required")

    svc = PaymentService(StripeProvider())
    try:
        result = await svc.revoke_subscription(
            session,
            subscription_id=sub_id,
            revoked_by=current_user.id,
            reason=reason,
        )
        await log_event(
            session, "subscription.revoked",
            f"Subscription {sub_id} revoked: {reason}",
            user_id=current_user.id,
        )
        await session.commit()
        return {"success": True, "subscription": result}
    except PaymentServiceError as e:
        raise HTTPException(e.status_code, str(e))


# ---------------------------------------------------------------------------
# GET /payments/pending — pending manual payments (includes crypto)
# ---------------------------------------------------------------------------
# (existing endpoint stays, new one below for crypto verification detail)


# ---------------------------------------------------------------------------
# GET /payments/pending — pending manual payments (cash + crypto)
# NOTE: must be registered BEFORE /payments/{payment_id} so "pending" is not
# captured as a payment_id (FastAPI matches routes in registration order).
# ---------------------------------------------------------------------------
@router.get("/payments/pending")
async def list_pending_manual_payments(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission(Permission.PAYMENTS_READ)),
):
    """List payments awaiting manual verification (cash or crypto).

    REQ 8: only payments the client has actually SUBMITTED appear here.
    Plain PENDING (created, not submitted) is invisible to the owner until
    the client submits proof — a created payment is not a verification
    request. Stale unsubmitted payments are swept to EXPIRED first.
    """
    from billing.payment_service import PaymentService
    from billing.stripe_provider import StripeProvider
    svc = PaymentService(StripeProvider())
    await svc.expire_stale_payments(session)

    pending_statuses = [
        "PENDING_VERIFICATION",
        "AWAITING_PAYMENT",
        "TRANSACTION_DETECTED",
        "CONFIRMING",
        "MANUAL_REVIEW",
    ]
    query = (
        select(Payment)
        .where(Payment.status.in_(pending_statuses))
        .order_by(Payment.created_at.asc())
    )
    count_query = select(func.count()).select_from(Payment).where(
        Payment.status.in_(pending_statuses)
    )
    total = (await session.execute(count_query)).scalar() or 0
    query = query.offset(offset).limit(limit)
    result = await session.execute(query)
    payments = result.scalars().all()
    return {
        "items": await _enrich_payments(session, payments),
        "total": total,
        "limit": limit,
        "offset": offset,
    }


# ---------------------------------------------------------------------------
# GET /payments/{payment_id} — detailed payment info (including crypto)
# ---------------------------------------------------------------------------
@router.get("/payments/{payment_id}")
async def get_payment_detail(
    payment_id: str,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission(Permission.PAYMENTS_READ)),
):
    """Get detailed payment information including crypto verification details."""
    payment = await session.get(Payment, payment_id)
    if not payment:
        raise HTTPException(404, "Payment not found")

    data = payment.to_dict()

    # Attach client identity for owner review
    user_result = await session.execute(
        select(User.email, User.first_name, User.last_name).where(User.id == payment.user_id)
    )
    urow = user_result.first()
    if urow:
        data["user_email"] = urow[0]
        data["user_first_name"] = urow[1]
        data["user_last_name"] = urow[2]

    # Enrich with crypto verification info if applicable
    if payment.payment_method_type == "manual_crypto":
        from billing.blockchain_service import get_network_config
        net_config = get_network_config(payment.deposit_network or "")
        data["crypto_info"] = {
            "network": payment.deposit_network,
            "ticker": payment.coin_ticker,
            "deposit_address": payment.deposit_address,
            "expected_amount": float(payment.expected_amount) if payment.expected_amount else None,
            "confirmations_required": net_config.get("confirmations_required", 0),
            "confirmation_count": payment.confirmation_count or 0,
            "verification_type": payment.verification_type,
            "verified_by": payment.verified_by,
        }

    return {"payment": data}


# ---------------------------------------------------------------------------
# POST /payments/{payment_id}/verify-crypto — owner/billing approve crypto
# ---------------------------------------------------------------------------
@router.post("/payments/{payment_id}/verify-crypto")
async def verify_crypto_payment(
    payment_id: str,
    body: dict = {},
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_admin_user),
    _=Depends(require_permission(Permission.PAYMENTS_VERIFY)),
):
    """
    Owner/Billing manually verify and approve a crypto payment.

    Works from TRANSACTION_DETECTED, CONFIRMING, or MANUAL_REVIEW status.
    """
    from billing.payment_service import PaymentService, PaymentServiceError
    from billing.stripe_provider import StripeProvider

    internal_notes = body.get("internal_notes", "")
    verification_type = body.get("verification_type", "owner_override")

    svc = PaymentService(StripeProvider())
    try:
        result = await svc.approve_crypto_manual_review(
            session,
            payment_id=payment_id,
            approved_by=current_user.id,
            internal_notes=internal_notes,
            verification_type=verification_type,
        )
        await log_event(
            session, "payment.crypto_approved",
            f"Crypto payment {result.get('payment_number', payment_id)} manually approved",
            user_id=current_user.id,
        )
        await session.commit()
        return {"success": True, "payment": result}
    except PaymentServiceError as e:
        raise HTTPException(e.status_code, str(e))


# ---------------------------------------------------------------------------
# POST /payments/{payment_id}/approve — approve manual payment (cash or crypto)
# ---------------------------------------------------------------------------
@router.post("/payments/{payment_id}/approve")
async def approve_manual_payment(
    payment_id: str,
    body: dict = {},
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_admin_user),
    _=Depends(require_permission(Permission.PAYMENTS_VERIFY)),
):
    """
    Approve a manual payment (cash or crypto).
    For cash: PENDING_VERIFICATION → PAID.
    For crypto: TRANSACTION_DETECTED/CONFIRMING/MANUAL_REVIEW → PAID.
    Idempotent: second approval returns existing payment.
    """
    from billing.payment_service import PaymentService, PaymentServiceError
    from billing.stripe_provider import StripeProvider

    payment = await session.get(Payment, payment_id)
    if not payment:
        raise HTTPException(404, "Payment not found")

    svc = PaymentService(StripeProvider())
    try:
        if payment.payment_method_type == "manual_crypto":
            result = await svc.approve_crypto_manual_review(
                session,
                payment_id=payment_id,
                approved_by=current_user.id,
                internal_notes=body.get("internal_notes"),
                verification_type="owner_override",
            )
        else:
            result = await svc.approve_manual_payment(
                session,
                payment_id=payment_id,
                approved_by=current_user.id,
                internal_notes=body.get("internal_notes"),
            )
        await log_event(
            session, "payment.approved",
            f"Payment {result.get('payment_number', payment_id)} approved",
            user_id=current_user.id,
        )
        await session.commit()
        return {"success": True, "payment": result}
    except PaymentServiceError as e:
        raise HTTPException(e.status_code, str(e))


# ---------------------------------------------------------------------------
# POST /payments/{payment_id}/reject — reject payment (works for all types)
# ---------------------------------------------------------------------------
@router.post("/payments/{payment_id}/reject")
async def reject_payment(
    payment_id: str,
    body: dict = {},
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_admin_user),
    _=Depends(require_permission(Permission.PAYMENTS_VERIFY)),
):
    """Reject a payment (manual or crypto). Transitions to FAILED."""
    from billing.payment_service import PaymentService, PaymentServiceError
    from billing.stripe_provider import StripeProvider

    rejection_reason = body.get("rejection_reason", "")
    if not rejection_reason:
        raise HTTPException(400, "Rejection reason is required")

    svc = PaymentService(StripeProvider())
    try:
        result = await svc.reject_manual_payment(
            session,
            payment_id=payment_id,
            rejection_reason=rejection_reason,
            rejected_by=current_user.id,
        )
        await log_event(
            session, "payment.rejected",
            f"Payment {result.get('payment_number', payment_id)} rejected: {rejection_reason}",
            user_id=current_user.id,
        )
        await session.commit()
        return {"success": True, "payment": result}
    except PaymentServiceError as e:
        raise HTTPException(e.status_code, str(e))


# ---------------------------------------------------------------------------
# Payments list (from real Payment table)
# ---------------------------------------------------------------------------
async def _enrich_payments(session: AsyncSession, payments: list[Payment]) -> list[dict]:
    """Attach client identity (email, name) to payment dicts for owner review.

    The owner must see WHO paid, not just a truncated user id.
    """
    user_ids = {p.user_id for p in payments}
    if not user_ids:
        return [p.to_dict() for p in payments]
    users_result = await session.execute(
        select(User.id, User.email, User.first_name, User.last_name).where(User.id.in_(user_ids))
    )
    users = {row[0]: row for row in users_result.all()}
    out = []
    for p in payments:
        d = p.to_dict()
        u = users.get(p.user_id)
        if u:
            d["user_email"] = u[1]
            d["user_first_name"] = u[2]
            d["user_last_name"] = u[3]
        out.append(d)
    return out


@router.get("/payments")
async def list_payments(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission(Permission.BILLING_READ)),
):
    query = select(Payment).order_by(Payment.created_at.desc())
    count_query = select(func.count()).select_from(Payment)
    total = (await session.execute(count_query)).scalar() or 0
    query = query.offset(offset).limit(limit)
    result = await session.execute(query)
    payments = result.scalars().all()
    return {
        "items": await _enrich_payments(session, payments),
        "total": total,
        "limit": limit,
        "offset": offset,
    }


# ---------------------------------------------------------------------------
# Payments list with optional filters
# ---------------------------------------------------------------------------
@router.get("/payments/list")
async def list_payments_filtered(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    status: str = Query(None),
    payment_method_type: str = Query(None),
    currency: str = Query(None),
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission(Permission.PAYMENTS_READ)),
):
    """List payments with optional filters for status, type, currency."""
    query = select(Payment)
    count_query = select(func.count()).select_from(Payment)

    if status:
        query = query.where(Payment.status == status)
        count_query = count_query.where(Payment.status == status)
    if payment_method_type:
        query = query.where(Payment.payment_method_type == payment_method_type)
        count_query = count_query.where(Payment.payment_method_type == payment_method_type)
    if currency:
        query = query.where(Payment.currency == currency)
        count_query = count_query.where(Payment.currency == currency)

    total = (await session.execute(count_query)).scalar() or 0
    query = query.order_by(Payment.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(query)
    payments = result.scalars().all()
    return {
        "items": await _enrich_payments(session, payments),
        "total": total,
        "limit": limit,
        "offset": offset,
    }


# ---------------------------------------------------------------------------
# Revenue Analytics (Super Admin)
# ---------------------------------------------------------------------------
@router.get("/analytics/revenue")
async def revenue_analytics(
    session: AsyncSession = Depends(get_session),
    _=Depends(require_role("owner")),
):
    # Active subscriptions
    active_subs_result = await session.execute(
        select(func.count()).select_from(Subscription).where(Subscription.active == True)
    )
    active_subs = active_subs_result.scalar() or 0

    # Total subscriptions
    total_subs_result = await session.execute(select(func.count()).select_from(Subscription))
    total_subs = total_subs_result.scalar() or 0

    # Total users
    users_result = await session.execute(select(func.count()).select_from(User))
    total_users = users_result.scalar() or 0

    # Active licenses
    active_licenses_result = await session.execute(
        select(func.count()).select_from(License).where(License.status == "active")
    )
    active_licenses = active_licenses_result.scalar() or 0

    # Connected accounts
    accounts_result = await session.execute(
        select(func.count()).select_from(TradingAccount).where(TradingAccount.active == True)
    )
    connected_accounts = accounts_result.scalar() or 0

    # MRR estimate from active subscriptions (use price field)
    mrr_result = await session.execute(
        select(func.coalesce(func.sum(Subscription.price), 0)).where(
            Subscription.active == True,
            Subscription.billing_cycle == "monthly",
        )
    )
    monthly_revenue = float(mrr_result.scalar() or 0)

    # Yearly subscriptions divided by 12 for MRR
    yearly_result = await session.execute(
        select(func.coalesce(func.sum(Subscription.price), 0)).where(
            Subscription.active == True,
            Subscription.billing_cycle == "yearly",
        )
    )
    yearly_revenue = float(yearly_result.scalar() or 0)
    mrr = monthly_revenue + (yearly_revenue / 12)
    arr = mrr * 12

    # Churn (users with cancelled subscriptions in last 30 days)
    since = datetime.now(timezone.utc) - timedelta(days=30)
    churned_result = await session.execute(
        select(func.count()).select_from(Subscription).where(
            Subscription.active == False,
            Subscription.end_date >= since,
        )
    )
    churned_30d = churned_result.scalar() or 0

    # New users in last 30 days
    new_users_result = await session.execute(
        select(func.count()).select_from(User).where(User.created_at >= since)
    )
    new_users_30d = new_users_result.scalar() or 0

    # Plan distribution
    plan_result = await session.execute(
        select(Subscription.plan, func.count().label("count"))
        .where(Subscription.active == True)
        .group_by(Subscription.plan)
    )
    plan_distribution = {row.plan: row.count for row in plan_result.all()}

    # Total revenue from real Payment table (only PAID transactions)
    payment_result = await session.execute(
        select(func.coalesce(func.sum(Payment.final_amount), 0)).where(
            Payment.status == "PAID",
        )
    )
    total_revenue = float(payment_result.scalar() or 0)

    # Refunds (deducted from revenue)
    refund_result = await session.execute(
        select(func.coalesce(func.sum(Payment.final_amount), 0)).where(
            Payment.status == "REFUNDED",
        )
    )
    total_refunds = float(refund_result.scalar() or 0)
    net_revenue = total_revenue - total_refunds

    return {
        "mrr": round(mrr, 2),
        "arr": round(arr, 2),
        "total_revenue": round(total_revenue, 2),
        "total_refunds": round(total_refunds, 2),
        "net_revenue": round(net_revenue, 2),
        "active_subscriptions": active_subs,
        "total_subscriptions": total_subs,
        "active_licenses": active_licenses,
        "connected_accounts": connected_accounts,
        "total_users": total_users,
        "churned_30d": churned_30d,
        "new_users_30d": new_users_30d,
        "plan_distribution": plan_distribution,
    }

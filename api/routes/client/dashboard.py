from __future__ import annotations

import copy
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.client_dashboard import ClientDashboardResponse
from api.services.client_dashboard_aggregator import ClientDashboardAggregator
from api.services.client_dashboard_query_service import ClientDashboardQueryService
from api.services.coupon_service import (
    VALID_CURRENCIES,
    CouponValidationError,
    generate_subscription_number,
    get_plan_price,
    validate_coupon_for_purchase,
)
from database.db import get_session
from database.models import (
    AuditLog,
    CouponRedemption,
    License,
    NewsEvent,
    PaperTrade,
    PlanDefinition,
    RiskProfile,
    Subscription,
    TradingAccount,
    User,
)
from security.auth import get_current_user
from security.audit import log_event
from shared_utils.timezone import is_valid_timezone

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/client", tags=["client"])


def _days_remaining(dt: datetime | None) -> int | None:
    if not dt:
        return None
    delta = (dt - datetime.now(timezone.utc)).days
    return max(delta, 0)


def _profile_payload(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "avatar": user.avatar,
        "country": user.country,
        "language": user.language,
        "timezone": user.timezone,
        "email_verified": user.email_verified,
        "telegram_id": user.telegram_id,
        "telegram_username": user.telegram_username,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


# ---------------------------------------------------------------------------
# GET /api/client/dashboard  (home)
# ---------------------------------------------------------------------------
@router.get("/dashboard", response_model=ClientDashboardResponse)
async def client_dashboard(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    read = await ClientDashboardQueryService(session).load_dashboard(current_user)
    return ClientDashboardAggregator().build(read)


# ---------------------------------------------------------------------------
# GET /api/client/profile
# ---------------------------------------------------------------------------
@router.get("/profile")
async def client_profile(
    current_user: User = Depends(get_current_user),
):
    return _profile_payload(current_user)


# ---------------------------------------------------------------------------
# PATCH /api/client/profile   (email is NOT editable — requires verification flow)
# ---------------------------------------------------------------------------
@router.patch("/profile")
async def update_client_profile(
    body: dict,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    allowed_fields = {"first_name", "last_name", "avatar", "country", "language", "timezone"}
    updates = {k: v for k, v in body.items() if k in allowed_fields and v is not None}
    if "language" in updates and str(updates["language"]).upper() not in {"EN", "AR", "FR", "ES"}:
        raise HTTPException(status_code=400, detail="Invalid language. Use EN, AR, FR or ES")
    if not updates:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    for k, v in updates.items():
        if k == "language":
            v = str(v).upper()
        setattr(current_user, k, v)
    await log_event(session, "client.profile_updated", "Client profile updated",
                    user_id=current_user.id, payload={"fields": sorted(updates.keys())})
    await session.commit()
    return {"message": "Profile updated", "profile": _profile_payload(current_user)}


@router.get("/overview")
async def client_overview(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    t_result = await session.execute(
        select(PaperTrade).where(
            PaperTrade.user_id == current_user.id,
            PaperTrade.status == "CLOSED",
        )
    )
    closed_trades = list(t_result.scalars().all())
    today_trades = [t for t in closed_trades if t.closed_at and t.closed_at >= today_start]

    open_result = await session.execute(
        select(PaperTrade).where(
            PaperTrade.user_id == current_user.id,
            PaperTrade.status.in_(["PLANNED", "FILLED"]),
        )
    )
    open_trades = list(open_result.scalars().all())

    accounts_result = await session.execute(
        select(TradingAccount).where(
            TradingAccount.user_id == current_user.id,
            TradingAccount.active == True,
        )
    )
    accounts = list(accounts_result.scalars().all())

    license_result = await session.execute(
        select(License).where(
            License.user_id == current_user.id,
            License.status == "active",
        )
    )
    active_license = license_result.scalar_one_or_none()

    total_pnl = sum(t.realized_pnl or 0 for t in closed_trades)
    today_pnl = sum(t.realized_pnl or 0 for t in today_trades)
    wins = sum(1 for t in closed_trades if t.realized_pnl and t.realized_pnl > 0)
    losses = sum(1 for t in closed_trades if t.realized_pnl and t.realized_pnl < 0)
    win_rate = round(wins / len(closed_trades) * 100, 1) if closed_trades else 0

    gw = sum(t.realized_pnl for t in closed_trades if t.realized_pnl and t.realized_pnl > 0)
    gl = abs(sum(t.realized_pnl for t in closed_trades if t.realized_pnl and t.realized_pnl < 0))
    profit_factor = round(gw / gl, 2) if gl > 0 else (gw if gw else 0)

    balance = accounts[0].balance_snapshot if accounts else 0
    equity = accounts[0].equity_snapshot if accounts else balance

    return {
        "balance": balance or 0,
        "equity": equity or 0,
        "today_pnl": round(today_pnl, 2),
        "total_pnl": round(total_pnl, 2),
        "floating": round(sum(t.realized_pnl or 0 for t in open_trades), 2),
        "open_trades_count": len(open_trades),
        "total_trades": len(closed_trades),
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "wins": wins,
        "losses": losses,
        "license_plan": active_license.plan if active_license else None,
        "license_status": active_license.status if active_license else None,
        "accounts_count": len(accounts),
    }


@router.get("/trades")
async def client_trades(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    status: str = Query("all", description="all, open, closed"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    conditions = [PaperTrade.user_id == current_user.id]
    if status == "open":
        conditions.append(PaperTrade.status.in_(["PLANNED", "FILLED"]))
    elif status == "closed":
        conditions.append(PaperTrade.status == "CLOSED")

    result = await session.execute(
        select(PaperTrade).where(*conditions).order_by(desc(PaperTrade.created_at)).offset(offset).limit(limit)
    )
    trades = result.scalars().all()

    count_result = await session.execute(select(func.count()).select_from(PaperTrade).where(*conditions))
    total = count_result.scalar() or 0

    return {
        "items": [
            {
                "id": t.id,
                "symbol": t.symbol,
                "direction": t.direction,
                "status": t.status,
                "entry_price": t.entry_price,
                "stop_loss": t.stop_loss,
                "take_profit": t.take_profit,
                "lot_size": t.lot_size,
                "realized_pnl": t.realized_pnl,
                "realized_r": t.realized_r,
                "close_reason": t.close_reason,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "closed_at": t.closed_at.isoformat() if t.closed_at else None,
                "partial_closed": t.partial_closed,
                "breakeven_activated": t.breakeven_activated,
                "validation_batch": t.validation_batch,
            }
            for t in trades
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/license")
async def client_license(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(License).where(License.user_id == current_user.id).order_by(desc(License.created_at))
    )
    licenses = result.scalars().all()

    accounts_result = await session.execute(
        select(TradingAccount).where(TradingAccount.user_id == current_user.id)
    )
    accounts = list(accounts_result.scalars().all())

    history_result = await session.execute(
        select(AuditLog)
        .where(
            AuditLog.user_id == current_user.id,
            AuditLog.event_type.ilike("license.%"),
        )
        .order_by(desc(AuditLog.created_at))
        .limit(10)
    )
    history = [
        {
            "event_type": h.event_type,
            "message": h.message,
            "details": h.payload_json,
            "created_at": h.created_at.isoformat() if h.created_at else None,
        }
        for h in history_result.scalars().all()
    ]

    return {
        "items": [
            {
                "id": l.id,
                "license_key": l.license_key,
                "plan": l.plan,
                "status": l.status,
                "max_accounts": l.max_accounts,
                "used_accounts": len([a for a in accounts if a.license_id == l.id]),
                "bound_account_id": l.bound_account_id,
                "bound_at": l.bound_at.isoformat() if l.bound_at else None,
                "transfer_locked": l.transfer_locked,
                "created_at": l.created_at.isoformat() if l.created_at else None,
                "expires_at": l.expires_at.isoformat() if l.expires_at else None,
                "days_remaining": _days_remaining(l.expires_at),
            }
            for l in licenses
        ],
        "total": len(licenses),
        "activation_history": history,
    }


# ---------------------------------------------------------------------------
# GET /api/client/subscription
# ---------------------------------------------------------------------------
async def _plan_lookup(session: AsyncSession, plan_id: str | None):
    if not plan_id:
        return None
    result = await session.execute(select(PlanDefinition).where(PlanDefinition.id == plan_id))
    return result.scalar_one_or_none()


@router.get("/subscription")
async def client_subscription(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    sub = current_user.subscription

    payments_result = await session.execute(
        select(AuditLog)
        .where(
            AuditLog.user_id == current_user.id,
            AuditLog.event_type.ilike("payment.%"),
        )
        .order_by(desc(AuditLog.created_at))
        .limit(20)
    )
    invoices = [
        {
            "id": p.id,
            "event_type": p.event_type,
            "message": p.message,
            "amount": (p.payload_json or {}).get("amount"),
            "currency": (p.payload_json or {}).get("currency", "USD"),
            "method": (p.payload_json or {}).get("method"),
            "status": "paid" if p.severity == "SUCCESS" else p.severity.lower(),
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in payments_result.scalars().all()
    ]
    payment_method = next((i["method"] for i in invoices if i["method"]), None)

    plans_result = await session.execute(
        select(PlanDefinition)
        .where(PlanDefinition.is_archived == False)
        .order_by(PlanDefinition.sort_order)
    )
    plans = [
        {
            "id": p.id,
            "name": p.name,
            "price_monthly": p.price_monthly,
            "price_yearly": p.price_yearly,
            "one_time_price": p.one_time_price,
            "max_accounts": p.max_accounts,
            "on_sale": p.on_sale,
            "old_price": p.old_price,
        }
        for p in plans_result.scalars().all()
    ]

    sub_payload = None
    if sub:
        plan_def = await _plan_lookup(session, sub.plan)
        sub_payload = {
            "plan": sub.plan,
            "plan_name": plan_def.name if plan_def else sub.plan,
            "active": bool(sub.active),
            "price": sub.price,
            "plan_price_paid": float(sub.plan_price_paid) if sub.plan_price_paid is not None else None,
            "plan_currency": sub.plan_currency,
            "billing_cycle": sub.billing_cycle,
            "start_date": sub.start_date.isoformat() if sub.start_date else None,
            "renew_date": sub.end_date.isoformat() if sub.end_date else None,
            "days_remaining": _days_remaining(sub.end_date),
        }

    return {
        "subscription": sub_payload,
        "payment_method": payment_method,
        "invoices": invoices,
        "available_plans": plans,
    }


# ---------------------------------------------------------------------------
# POST /api/client/subscription  (subscribe to a plan)
# ---------------------------------------------------------------------------
@router.post("/subscription")
async def subscribe_to_plan(
    body: dict,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """DEPRECATED: Use POST /api/client/checkout instead.

    This endpoint now creates a checkout session via the payment provider
    rather than directly activating a subscription.

    Body: ``{plan_id, currency?, coupon_code?}``

    Returns a checkout URL that the client must redirect to for payment.
    """
    from api.routes.client.payments import _get_payment_service_for_method
    from billing.payment_service import PaymentServiceError
    from api.services.coupon_service import get_plan_price as _get_plan_price

    plan_id = str(body.get("plan_id") or "").strip()
    currency = str(body.get("currency") or current_user.billing_currency or "USD").strip().upper()
    coupon_code = str(body.get("coupon_code") or "").strip().upper() or None

    if not plan_id:
        raise HTTPException(status_code=400, detail="plan_id is required")

    # Check for an existing ACTIVE subscription (only one allowed at a time)
    active_result = await session.execute(
        select(Subscription).where(
            Subscription.user_id == current_user.id,
            Subscription.active == True,
            Subscription.status == "ACTIVE",
        )
    )
    if active_result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="You already have an active subscription")

    plan_result = await session.execute(select(PlanDefinition).where(PlanDefinition.id == plan_id))
    plan = plan_result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if plan.is_archived:
        raise HTTPException(status_code=400, detail="Plan is archived and cannot be subscribed to")

    if currency not in VALID_CURRENCIES:
        raise HTTPException(status_code=400, detail=f"currency must be one of: {', '.join(sorted(VALID_CURRENCIES))}")

    original_price = await _get_plan_price(plan, currency)
    if original_price is None:
        raise HTTPException(status_code=400, detail=f"Plan '{plan.id}' has no price configured for {currency}")

    # Validate coupon (if provided)
    discount_amount = Decimal("0")
    final_price = original_price
    coupon_obj = None
    if coupon_code:
        try:
            coupon_obj, original_price, discount_amount, final_price = await validate_coupon_for_purchase(
                session, code=coupon_code, user_id=current_user.id, plan=plan, currency=currency,
            )
        except CouponValidationError as exc:
            raise HTTPException(status_code=exc.status_code, detail=f"Coupon error: {exc.message}")

    # Create checkout session via payment service
    svc = _get_payment_service_for_method()
    import os
    base_url = os.getenv("APP_BASE_URL", "http://localhost:3000")

    try:
        result = await svc.create_checkout(
            session,
            user=current_user,
            plan=plan,
            currency=currency,
            coupon=coupon_obj,
            original_price=original_price,
            discount_amount=discount_amount,
            final_price=final_price,
            success_url=f"{base_url}/dashboard/subscription?payment=success",
            cancel_url=f"{base_url}/dashboard/subscription?payment=cancelled",
        )
        await session.commit()
        return {
            "success": True,
            "checkout": result,
            "message": "Redirect to checkout_url to complete payment",
        }
    except PaymentServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except Exception as e:
        logger.exception("subscribe_to_plan: checkout creation failed")
        await session.rollback()
        raise HTTPException(status_code=500, detail="Failed to create checkout")


# ---------------------------------------------------------------------------
# POST /api/client/subscription/cancel
# ---------------------------------------------------------------------------
@router.post("/subscription/cancel")
async def cancel_client_subscription(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    sub = current_user.subscription
    if not sub:
        raise HTTPException(status_code=404, detail="No subscription found")
    sub.active = False
    sub.status = "CANCELLED"
    sub.end_date = datetime.now(timezone.utc)
    await log_event(session, "subscription.cancelled", "Client cancelled subscription",
                    user_id=current_user.id, severity="WARNING")
    await session.commit()
    return {"message": "Subscription cancelled"}


# ---------------------------------------------------------------------------
# POST /api/client/subscription/renew
# ---------------------------------------------------------------------------
@router.post("/subscription/renew")
async def renew_client_subscription(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Renew a subscription by creating a new checkout session.

    Free renewals are no longer available. The client must go through
    the payment flow for every renewal.
    """
    sub = current_user.subscription
    if not sub:
        raise HTTPException(status_code=404, detail="No subscription found")

    # Find the plan for this subscription
    plan = await _plan_lookup(session, sub.plan)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    if plan.is_archived:
        raise HTTPException(status_code=400, detail="Plan is no longer available")

    # Redirect to checkout flow
    currency = sub.plan_currency or "USD"
    from api.routes.client.payments import _get_payment_service_for_method
    from billing.payment_service import PaymentServiceError

    svc = _get_payment_service_for_method()
    import os
    base_url = os.getenv("APP_BASE_URL", "http://localhost:3000")

    original_price = await get_plan_price(plan, currency)
    if original_price is None:
        raise HTTPException(status_code=400, detail=f"Plan has no {currency} pricing")

    try:
        result = await svc.create_checkout(
            session,
            user=current_user,
            plan=plan,
            currency=currency,
            coupon=None,  # No coupon auto-applied on renewal
            original_price=original_price,
            discount_amount=Decimal("0"),
            final_price=original_price,
            success_url=f"{base_url}/dashboard/subscription?payment=success",
            cancel_url=f"{base_url}/dashboard/subscription?payment=cancelled",
        )
        await session.commit()
        return {
            "success": True,
            "checkout": result,
            "message": "Redirect to checkout_url to complete renewal payment",
        }
    except PaymentServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except Exception as e:
        logger.exception("renew_client_subscription: checkout creation failed")
        await session.rollback()
        raise HTTPException(status_code=500, detail="Failed to create checkout")


# ---------------------------------------------------------------------------
# GET /api/client/subscription/history  (all past + current subscriptions)
# ---------------------------------------------------------------------------
@router.get("/subscription/history")
async def subscription_history(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Return all subscriptions for the authenticated client (newest first).

    Each row preserves the full purchase snapshot so historical records
    are never lost even when the client buys a new plan.
    """
    result = await session.execute(
        select(Subscription)
        .where(Subscription.user_id == current_user.id)
        .order_by(Subscription.created_at.desc())
    )
    subs = result.scalars().all()
    return {
        "subscriptions": [
            {
                "id": s.id,
                "subscription_number": s.subscription_number,
                "plan": s.plan,
                "plan_name": s.plan_name,
                "plan_currency": s.plan_currency,
                "plan_price_paid": float(s.plan_price_paid) if s.plan_price_paid else None,
                "active": bool(s.active),
                "billing_cycle": s.billing_cycle,
                "coupon_code": s.coupon_code,
                "discount_amount": float(s.discount_amount) if s.discount_amount else None,
                "start_date": s.start_date.isoformat() if s.start_date else None,
                "end_date": s.end_date.isoformat() if s.end_date else None,
                "days_remaining": _days_remaining(s.end_date) if s.active else 0,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in subs
        ]
    }


@router.get("/settings")
async def client_settings(
    current_user: User = Depends(get_current_user),
):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "language": current_user.language,
        "timezone": current_user.timezone,
        "billing_currency": current_user.billing_currency,
        "email_verified": current_user.email_verified,
        "telegram_id": current_user.telegram_id,
        "telegram_username": current_user.telegram_username,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        "preferences": _merged_preferences(current_user),
    }


DEFAULT_PREFERENCES: dict = {
    "theme": "system",
    # News alerts: controls whether the client receives economic-calendar/news
    # notifications. Does NOT enable/disable trading around news.
    # Economic Calendar T-60 protection is engine-controlled and always active.
    "news_alerts_enabled": True,
    "email_notifications": True,
    "telegram_notifications": True,
    "notifications": {
        "signals": True, "filled": True, "tp": True, "sl": True,
        "news": True, "weekly_report": True, "monthly_report": True,
    },
}

LANGUAGES = {"EN", "AR", "FR", "ES"}
NOTIFICATION_KEYS = {"signals", "filled", "tp", "sl", "news", "weekly_report", "monthly_report"}


def _deep_merge(base: dict, extra: dict) -> dict:
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def _merged_preferences(user: User) -> dict:
    base = copy.deepcopy(DEFAULT_PREFERENCES)
    stored = user.preferences or {}
    if isinstance(stored, dict):
        _deep_merge(base, stored)
    return base


def _validate_preferences(partial: dict) -> dict:
    """Validate a partial preferences object; raise 400 on invalid values.

    Client-configurable settings are limited to actual user preferences.
    Trading parameters (symbols, timeframes, sessions, risk, news block times)
    are controlled by AccountProfile → RiskProfile → TradingMode → ExecutionGuard.
    News alerts are notification-only — they do NOT control trading behavior.
    """
    clean: dict = {}
    if "theme" in partial:
        if partial["theme"] not in {"dark", "light", "system"}:
            raise HTTPException(status_code=400, detail="theme must be dark, light or system")
        clean["theme"] = partial["theme"]
    if "news_alerts_enabled" in partial:
        # News alerts: notification preference only. Does NOT control trading.
        # Economic Calendar T-60 protection is always active regardless of this setting.
        clean["news_alerts_enabled"] = bool(partial["news_alerts_enabled"])
    if "email_notifications" in partial:
        clean["email_notifications"] = bool(partial["email_notifications"])
    if "telegram_notifications" in partial:
        clean["telegram_notifications"] = bool(partial["telegram_notifications"])
    if "notifications" in partial:
        notifs = partial["notifications"]
        if not isinstance(notifs, dict):
            raise HTTPException(status_code=400, detail="notifications must be an object")
        invalid = set(notifs.keys()) - NOTIFICATION_KEYS
        if invalid:
            raise HTTPException(status_code=400, detail=f"Invalid notification keys: {sorted(invalid)}")
        clean["notifications"] = {k: bool(v) for k, v in notifs.items()}
    return clean


@router.patch("/settings")
async def update_client_settings(
    body: dict,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    scalar_fields = {"first_name", "last_name", "language", "timezone"}
    updates = {k: v for k, v in body.items() if k in scalar_fields and v is not None}

    if "language" in updates:
        language = str(updates["language"]).upper()
        if language not in LANGUAGES:
            raise HTTPException(status_code=400, detail="Invalid language. Use EN, AR, FR or ES")
        updates["language"] = language

    if "timezone" in updates:
        tz = str(updates["timezone"]).strip()
        if tz and not is_valid_timezone(tz):
            raise HTTPException(status_code=400, detail="Invalid timezone. Use a valid IANA timezone (e.g. Africa/Casablanca, Europe/Paris).")
        updates["timezone"] = tz if tz else None

    # Billing currency: USD/EUR/MAD, or null to clear back to the default
    billing_currency_updated = False
    if "billing_currency" in body:
        raw_currency = body["billing_currency"]
        if raw_currency is None or raw_currency == "":
            current_user.billing_currency = None
        else:
            currency = str(raw_currency).strip().upper()
            if currency not in VALID_CURRENCIES:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid billing_currency. Use one of: {', '.join(sorted(VALID_CURRENCIES))} or null",
                )
            current_user.billing_currency = currency
        billing_currency_updated = True

    for k, v in updates.items():
        setattr(current_user, k, v)

    prefs = dict(current_user.preferences or {})
    if "preferences" in body:
        if not isinstance(body["preferences"], dict):
            raise HTTPException(status_code=400, detail="preferences must be an object")
        partial = _validate_preferences(body["preferences"])
        _deep_merge(prefs, partial)
    elif any(k in DEFAULT_PREFERENCES for k in body):
        partial = _validate_preferences(body)
        _deep_merge(prefs, partial)

    if prefs:
        current_user.preferences = prefs

    if not updates and not prefs and not billing_currency_updated:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    updated_fields = sorted(
        set(updates.keys()) | set(prefs.keys()) | ({"billing_currency"} if billing_currency_updated else set())
    )
    await log_event(session, "client.settings_updated", "Client updated settings",
                    user_id=current_user.id,
                    payload={"fields": updated_fields})
    await session.commit()
    return {
        "message": "Settings updated",
        "updated": updated_fields,
        "billing_currency": current_user.billing_currency,
        "preferences": _merged_preferences(current_user),
    }


# ---------------------------------------------------------------------------
# GET /api/client/plans  (public plan catalog for authenticated clients)
# ---------------------------------------------------------------------------
@router.get("/plans")
async def list_client_plans(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Return active (non-archived) plans with multi-currency pricing.

    This is the client-facing equivalent of the admin ``GET /api/admin/plans``
    but without subscriber counts or promotion data.
    """
    result = await session.execute(
        select(PlanDefinition)
        .where(PlanDefinition.is_archived == False)
        .order_by(PlanDefinition.sort_order)
    )
    plans = result.scalars().all()
    return {
        "plans": [
            {
                "id": p.id,
                "name": p.name,
                "price_usd": float(p.price_usd) if p.price_usd is not None else None,
                "price_eur": float(p.price_eur) if p.price_eur is not None else None,
                "price_mad": float(p.price_mad) if p.price_mad is not None else None,
                "duration_days": p.duration_days,
                "max_accounts": p.max_accounts,
                "features_json": p.features_json or p.features or {},
                "description": p.description,
                "badge": p.badge,
                "display_order": p.display_order,
            }
            for p in plans
        ]
    }


# ---------------------------------------------------------------------------
# POST /api/client/coupons/validate  (purchase preview for the current user)
# ---------------------------------------------------------------------------
@router.post("/coupons/validate")
async def client_validate_coupon(
    body: dict,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Validate a coupon against a plan/currency for the authenticated client.

    Body: ``{code, plan_id, currency}`` — the user is always the current user.
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


@router.get("/performance")
async def client_performance(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(PaperTrade).where(
            PaperTrade.user_id == current_user.id,
            PaperTrade.status == "CLOSED",
        ).order_by(PaperTrade.closed_at)
    )
    trades = list(result.scalars().all())

    if not trades:
        return {
            "total_trades": 0,
            "net_pnl": 0,
            "profit_factor": 0,
            "win_rate": 0,
            "avg_r": 0,
            "max_drawdown": 0,
            "by_symbol": [],
            "by_month": [],
            "equity_curve": [],
        }

    wins = [t for t in trades if t.realized_pnl and t.realized_pnl > 0]
    losses = [t for t in trades if t.realized_pnl and t.realized_pnl < 0]
    gw = sum(t.realized_pnl for t in wins)
    gl = abs(sum(t.realized_pnl for t in losses))
    pf = round(gw / gl, 2) if gl > 0 else (gw if gw else 0)

    r_vals = [t.realized_r for t in trades if t.realized_r is not None]

    cum = 0
    peak = 0
    mdd = 0
    equity = []
    for t in trades:
        cum += (t.realized_pnl or 0)
        if cum > peak:
            peak = cum
        dd = peak - cum
        if dd > mdd:
            mdd = dd
        equity.append({"date": t.closed_at.isoformat() if t.closed_at else None, "equity": round(cum, 2)})

    by_symbol = {}
    for t in trades:
        sym = t.symbol or "UNKNOWN"
        if sym not in by_symbol:
            by_symbol[sym] = {"symbol": sym, "trades": 0, "pnl": 0, "wins": 0, "losses": 0}
        by_symbol[sym]["trades"] += 1
        by_symbol[sym]["pnl"] += (t.realized_pnl or 0)
        if t.realized_pnl and t.realized_pnl > 0:
            by_symbol[sym]["wins"] += 1
        elif t.realized_pnl and t.realized_pnl < 0:
            by_symbol[sym]["losses"] += 1

    by_month = {}
    for t in trades:
        if t.closed_at:
            m = t.closed_at.strftime("%Y-%m")
            if m not in by_month:
                by_month[m] = {"month": m, "trades": 0, "pnl": 0}
            by_month[m]["trades"] += 1
            by_month[m]["pnl"] += (t.realized_pnl or 0)

    return {
        "total_trades": len(trades),
        "net_pnl": round(sum(t.realized_pnl for t in trades), 2),
        "profit_factor": pf,
        "win_rate": round(len(wins) / len(trades) * 100, 1),
        "avg_r": round(sum(r_vals) / len(r_vals), 2) if r_vals else 0,
        "max_drawdown": round(mdd, 2),
        "by_symbol": list(by_symbol.values()),
        "by_month": sorted(by_month.values(), key=lambda x: x["month"]),
        "equity_curve": equity,
    }


# ---------------------------------------------------------------------------
# Trading Mode (per-account)
# ---------------------------------------------------------------------------
VALID_TRADING_MODES = {"conservative", "balanced", "aggressive"}


@router.get("/accounts/{account_id}/trading-mode")
async def get_trading_mode(
    account_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Return the current trading mode for an account's risk profile."""
    result = await session.execute(
        select(TradingAccount).where(
            TradingAccount.id == account_id,
            TradingAccount.user_id == current_user.id,
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    if not account.risk_profile:
        raise HTTPException(status_code=404, detail="No risk profile configured for this account")

    return {
        "account_id": account.id,
        "trading_mode": account.risk_profile.mode,
    }


@router.patch("/accounts/{account_id}/trading-mode")
async def update_trading_mode(
    account_id: str,
    body: dict,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Update the trading mode for an account's risk profile."""
    mode = (body.get("trading_mode") or "").strip().lower()
    if mode not in VALID_TRADING_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid trading_mode. Must be one of: {', '.join(sorted(VALID_TRADING_MODES))}",
        )

    result = await session.execute(
        select(TradingAccount).where(
            TradingAccount.id == account_id,
            TradingAccount.user_id == current_user.id,
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    if not account.risk_profile:
        raise HTTPException(status_code=404, detail="No risk profile configured for this account")

    old_mode = account.risk_profile.mode
    account.risk_profile.mode = mode

    # Also sync TradingAccount.trade_mode so the engine reads the correct value.
    # The engine reads account.trade_mode (not risk_profiles.mode).
    account.trade_mode = mode.upper()

    await log_event(
        session,
        "client.trading_mode_changed",
        f"Trading mode changed from {old_mode} to {mode}",
        user_id=current_user.id,
        account_id=account.id,
        payload={"old_mode": old_mode, "new_mode": mode},
    )
    await session.commit()
    return {"message": "Trading mode updated", "trading_mode": mode}


# ---------------------------------------------------------------------------
# Account Risk Profile
# ---------------------------------------------------------------------------
@router.get("/accounts/{account_id}/risk")
async def get_account_risk(
    account_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Return live risk status for an account — single source of truth."""
    from core_engine.risk.live_risk_calculator import live_risk_calculator, OpenPosition
    from core_engine.risk.prop_firm_detector import prop_firm_detector, VerificationStatus

    # Load account
    result = await session.execute(
        select(TradingAccount).where(
            TradingAccount.id == account_id,
            TradingAccount.user_id == current_user.id,
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # Load risk profile
    risk_profile_data = None
    if account.risk_profile:
        rp = account.risk_profile
        risk_profile_data = {
            "initial_balance": rp.initial_balance,
            "day_start_balance": rp.day_start_balance,
            "day_start_equity": rp.day_start_equity,
            "high_water_mark": rp.daily_high_equity,  # trailing max equity
            "daily_loss": rp.daily_loss,
            "max_loss": rp.max_loss,
            "drawdown_type": rp.drawdown_type,
            "mode": rp.mode,
            "max_risk_trade": rp.max_risk_trade,
            "profit_target": rp.profit_target,
            "safety_buffer_pct": rp.safety_buffer_pct,
        }

    # Load open positions
    open_result = await session.execute(
        select(PaperTrade).where(
            PaperTrade.account_id == account_id,
            PaperTrade.status == "OPEN",
        )
    )
    open_trades = open_result.scalars().all()
    open_positions = [
        OpenPosition(
            id=t.id,
            symbol=t.symbol,
            direction=t.direction,
            entry_price=t.entry_price or 0,
            lot_size=t.lot_size or 0,
            stop_loss=t.stop_loss,
            take_profit=t.take_profit,
            unrealized_pnl=t.unrealized_pnl or 0,
        )
        for t in open_trades
    ]

    # Today's realized P&L
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_result = await session.execute(
        select(func.coalesce(func.sum(PaperTrade.realized_pnl), 0)).where(
            PaperTrade.account_id == account_id,
            PaperTrade.status == "CLOSED",
            PaperTrade.closed_at >= today_start,
        )
    )
    today_realized_pnl = float(today_result.scalar() or 0)

    # Today's floating P&L
    today_floating = sum(t.unrealized_pnl or 0 for t in open_trades)

    # Total realized loss
    total_loss_result = await session.execute(
        select(func.coalesce(func.sum(PaperTrade.realized_pnl), 0)).where(
            PaperTrade.account_id == account_id,
            PaperTrade.status == "CLOSED",
            PaperTrade.realized_pnl < 0,
        )
    )
    total_realized_loss = abs(float(total_loss_result.scalar() or 0))

    # Prop firm detection
    detection = prop_firm_detector.detect(
        server=account.server,
        broker=account.broker,
        company=None,
        account_name=account.name,
        user_declared_firm=account.prop_firm,
    )

    # Calculate risk status
    status = live_risk_calculator.calculate(
        account_id=account.id,
        account_type=account.account_type or "UNKNOWN",
        balance=account.balance_snapshot or 0,
        equity=account.equity_snapshot or 0,
        risk_profile=risk_profile_data,
        open_positions=open_positions,
        today_realized_pnl=today_realized_pnl,
        today_floating_pnl=today_floating,
        total_realized_loss_usd=total_realized_loss,
        last_scan_at=account.scans[-1].created_at.isoformat() if account.scans else None,
        trading_mode=account.trade_mode or "BALANCED",
        prop_firm=account.prop_firm,
        prop_firm_program=account.program,
        verification_status=detection.status.value,
    )

    return status.to_dict()

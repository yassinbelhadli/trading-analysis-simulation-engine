"""Coupon validation and discount calculation service.

Single source of truth for coupon eligibility checks — used by the admin
coupon routes, the admin subscription-creation route and the client
coupon-preview route. All money math uses Decimal; floats are never used
for currency values.
"""
from __future__ import annotations

import secrets
import string
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Coupon, CouponRedemption, PlanDefinition

VALID_CURRENCIES = {"USD", "EUR", "MAD"}


class CouponValidationError(Exception):
    """Raised when a coupon cannot be applied; carries an HTTP status code."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _as_decimal(value) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


async def get_plan_price(plan: PlanDefinition, currency: str) -> Decimal | None:
    """Return the plan price for a currency, or None if not configured."""
    attr = {"USD": plan.price_usd, "EUR": plan.price_eur, "MAD": plan.price_mad}.get(currency)
    return _as_decimal(attr) if attr is not None else None


async def validate_coupon_for_purchase(
    session: AsyncSession,
    *,
    code: str,
    user_id: str,
    plan: PlanDefinition,
    currency: str,
) -> tuple[Coupon, Decimal, Decimal, Decimal]:
    """Validate a coupon against a plan/currency for a user.

    Returns ``(coupon, original_price, discount_amount, final_price)``.
    Raises :class:`CouponValidationError` with a user-safe message when the
    coupon is invalid or any eligibility rule fails.
    """
    currency = (currency or "").strip().upper()
    if currency not in VALID_CURRENCIES:
        raise CouponValidationError(f"Invalid currency. Use one of: {', '.join(sorted(VALID_CURRENCIES))}")

    result = await session.execute(select(Coupon).where(Coupon.code == code))
    coupon = result.scalar_one_or_none()
    if not coupon:
        raise CouponValidationError("Coupon not found", status_code=404)
    if not coupon.active:
        raise CouponValidationError("Coupon is inactive")

    now = datetime.now(timezone.utc)
    if coupon.valid_from and now < coupon.valid_from:
        raise CouponValidationError("Coupon is not valid yet")
    if coupon.valid_until and now > coupon.valid_until:
        raise CouponValidationError("Coupon has expired")

    if coupon.max_redemptions is not None and coupon.total_redemptions >= coupon.max_redemptions:
        raise CouponValidationError("Coupon redemption limit reached")

    # Per-user limit: count this user's redemptions of this coupon
    per_user_result = await session.execute(
        select(func.count())
        .select_from(CouponRedemption)
        .where(
            CouponRedemption.coupon_id == coupon.id,
            CouponRedemption.user_id == user_id,
        )
    )
    user_redemptions = per_user_result.scalar() or 0
    if user_redemptions >= (coupon.max_per_user or 1):
        raise CouponValidationError("You have already used this coupon the maximum number of times")

    # Plan eligibility: applicable_plans null/empty means all plans
    applicable = coupon.applicable_plans
    if applicable and plan.id not in applicable:
        raise CouponValidationError("Coupon does not apply to this plan")

    original_price = await get_plan_price(plan, currency)
    if original_price is None:
        raise CouponValidationError(f"Plan '{plan.id}' has no price configured for {currency}")

    if coupon.min_subscription_value is not None:
        min_value = _as_decimal(coupon.min_subscription_value)
        if original_price < min_value:
            raise CouponValidationError(
                f"Minimum subscription value for this coupon is {min_value} {currency}"
            )

    discount_value = _as_decimal(coupon.discount_value)
    if coupon.discount_type == "percentage":
        if discount_value < 0 or discount_value > 100:
            raise CouponValidationError("Invalid coupon configuration")
        discount_amount = (original_price * discount_value / Decimal("100")).quantize(Decimal("0.01"))
    elif coupon.discount_type == "fixed_amount":
        # Fixed-amount discounts only apply in the coupon's own currency
        if (coupon.currency or "").upper() != currency:
            raise CouponValidationError(
                f"Coupon is only valid for {(coupon.currency or '').upper()} purchases"
            )
        discount_amount = discount_value.quantize(Decimal("0.01"))
    else:
        raise CouponValidationError("Invalid coupon configuration")

    # Never negative — clamp at zero
    final_price = max(Decimal("0"), original_price - discount_amount)

    return coupon, original_price, discount_amount, final_price


def generate_subscription_number() -> str:
    """Generate a human-readable subscription number: SUB-XXXXXXXX."""
    alphabet = string.ascii_uppercase + string.digits
    rand = "".join(secrets.choice(alphabet) for _ in range(8))
    return f"SUB-{rand}"

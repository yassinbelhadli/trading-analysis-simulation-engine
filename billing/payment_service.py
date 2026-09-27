"""
Payment service — single source of truth for payment state machine,
checkout creation, webhook processing, and idempotency.

All payment state transitions go through this service.
"""
from __future__ import annotations

import logging
import secrets
import string
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from billing.provider import PaymentProvider, PaymentProviderError, ProviderState, WebhookEvent
from database.models import (
    Coupon,
    CouponRedemption,
    License,
    Payment,
    PlanDefinition,
    Receipt,
    Subscription,
    User,
)

# Email imports — non-blocking. Failures are logged, never propagated.
try:
    from api.services.email_service import (
        BILLING_EMAIL,
        send_manual_payment_instructions_email,
        send_manual_payment_submitted_email,
        send_manual_payment_approved_email,
        send_manual_payment_rejected_email,
        send_payment_expired_email,
        send_subscription_activated_email,
        send_payment_failed_email,
        send_payment_success_email,
    )
    _EMAIL_AVAILABLE = True
except ImportError:
    _EMAIL_AVAILABLE = False

logger = logging.getLogger(__name__)

VALID_CURRENCIES = {"USD", "EUR", "MAD"}


async def _safe_send(coro) -> None:
    """Send an email coroutine without blocking or raising.

    All email failures are logged and swallowed so payment flow is never
    interrupted by transient SMTP issues.
    """
    if not _EMAIL_AVAILABLE:
        return
    try:
        await coro
    except Exception as e:
        logger.warning("Email delivery failed (non-blocking): %s", e)

# Allowed transition map (mirrors model but centralized here)
# PENDING → PAID is allowed because some providers send a single "completed"
# event without a separate processing step.
# PENDING_VERIFICATION is for manual payments awaiting owner/billing approval.
# Crypto-specific states: AWAITING_PAYMENT → TRANSACTION_DETECTED → CONFIRMING → PAID
# EXPIRED: manual payments never submitted before their deadline (REQ 7/9)
# REJECTED: manual payments whose proof was refused by the owner (REQ 17)
TRANSITIONS = {
    "PENDING": ["PROCESSING", "PAID", "CANCELLED", "FAILED", "PENDING_VERIFICATION", "EXPIRED"],
    "PROCESSING": ["PAID", "FAILED", "CANCELLED"],
    "PENDING_VERIFICATION": ["PAID", "FAILED", "CANCELLED", "REJECTED"],
    "AWAITING_PAYMENT": ["TRANSACTION_DETECTED", "EXPIRED", "CANCELLED"],
    "TRANSACTION_DETECTED": ["CONFIRMING", "AMOUNT_MISMATCH", "WRONG_NETWORK", "MANUAL_REVIEW"],
    "CONFIRMING": ["PAID", "FAILED", "MANUAL_REVIEW"],
    "MANUAL_REVIEW": ["PAID", "FAILED"],
    "EXPIRED": [],
    "REJECTED": [],
    "AMOUNT_MISMATCH": ["MANUAL_REVIEW"],
    "WRONG_NETWORK": [],
    "PAID": ["REFUNDED", "SUSPENDED"],
    "SUSPENDED": ["PAID", "REFUNDED"],
    "FAILED": [],
    "CANCELLED": [],
    "REFUNDED": [],
}


def _generate_payment_number() -> str:
    """Generate a unique payment number like PAY-A1B2C3D4."""
    alphabet = string.ascii_uppercase + string.digits
    suffix = "".join(secrets.choice(alphabet) for _ in range(8))
    return f"PAY-{suffix}"


def _generate_receipt_number() -> str:
    """Generate a unique receipt number like RCP-X1Y2Z3W4."""
    alphabet = string.ascii_uppercase + string.digits
    suffix = "".join(secrets.choice(alphabet) for _ in range(8))
    return f"RCP-{suffix}"


class PaymentServiceError(Exception):
    """Raised when a payment operation fails at the service level."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class PaymentService:
    """
    Handles all payment lifecycle operations:
    - Checkout creation (creates Payment + PENDING Subscription)
    - Webhook processing (transitions Payment status, activates Subscription)
    - Payment status queries
    - Receipt generation

    All methods are async and require a database session.
    """

    def __init__(self, provider: PaymentProvider):
        self.provider = provider

    # ------------------------------------------------------------------
    # Checkout creation
    # ------------------------------------------------------------------
    async def create_checkout(
        self,
        session: AsyncSession,
        *,
        user: User,
        plan: PlanDefinition,
        currency: str,
        coupon: Optional[Coupon] = None,
        original_price: Decimal,
        discount_amount: Decimal,
        final_price: Decimal,
        success_url: str,
        cancel_url: str,
        payment_method_type: str = "automatic",
        manual_instructions: Optional[str] = None,
        owner_config: Optional[dict] = None,
    ) -> dict:
        """
        Create a checkout session.

        Flow:
        1. Validate currency
        2. Create Payment record (PENDING)
        3. Create Subscription record (PENDING, active=False)
        4. For automatic: Create checkout session with provider
           For manual: Store instructions, no provider call
        5. Return checkout info + payment instructions

        The subscription is NOT activated until payment is confirmed
        via webhook, admin approval, or confirm_payment().
        """
        if currency not in VALID_CURRENCIES:
            raise PaymentServiceError(f"Invalid currency: {currency}")

        if not self.provider.is_configured:
            raise PaymentServiceError(
                "Payment provider is not configured. Please contact support.",
                status_code=503,
            )

        now = datetime.now(timezone.utc)

        # Expire stale manual payments before idempotency lookup so an old
        # never-submitted payment can never block a fresh checkout (REQ 9).
        await self.expire_stale_payments(session, now=now)

        # Check for existing PENDING checkout for this user + plan + currency
        # + payment method (idempotency). The method is part of the key so a
        # client switching from e.g. wafa_cash to cih_bank never receives the
        # other method's payment/instructions. Payments whose deadline already
        # passed are treated as expired (not reusable) even if the sweep above
        # has not committed yet.
        existing = await session.execute(
            select(Payment).where(
                Payment.user_id == user.id,
                Payment.plan_id == plan.id,
                Payment.currency == currency,
                Payment.payment_method == self.provider.name,
                Payment.status.in_(["PENDING", "PENDING_VERIFICATION"]),
                (Payment.expired_at.is_(None) | (Payment.expired_at > now)),
            )
        )
        existing_payment = existing.scalar_one_or_none()
        if existing_payment:
            if existing_payment.status in ("PENDING", "PENDING_VERIFICATION"):
                return {
                    "payment_id": existing_payment.id,
                    "payment_number": existing_payment.payment_number,
                    "checkout_url": "",
                    "checkout_id": existing_payment.provider_checkout_id or "",
                    "subscription_id": existing_payment.subscription_id,
                    "subscription_number": "",
                    "status": existing_payment.status,
                    "payment_method_type": existing_payment.payment_method_type,
                    "manual_instructions": existing_payment.manual_instructions,
                    "manual_reference": existing_payment.manual_reference,
                    "expired_at": existing_payment.expired_at.isoformat() if existing_payment.expired_at else None,
                    "reference_required": True,
                }

        # Create Payment record
        payment_number = _generate_payment_number()

        payment = Payment(
            payment_number=payment_number,
            user_id=user.id,
            plan_id=plan.id,
            coupon_id=coupon.id if coupon else None,
            original_amount=original_price,
            discount_amount=discount_amount,
            final_amount=final_price,
            currency=currency,
            payment_provider=self.provider.name,
            payment_method=self.provider.name,  # preserve method at checkout (never "—")
            payment_method_type=payment_method_type,
            status="PENDING",
            plan_name=plan.name,
            plan_duration_days=plan.duration_days,
            coupon_code=coupon.code if coupon else None,
            manual_instructions=manual_instructions,
            created_at=now,
            updated_at=now,
        )
        session.add(payment)
        await session.flush()  # Get payment.id

        # Create Subscription record (PENDING, inactive)
        from api.services.coupon_service import generate_subscription_number
        subscription_number = generate_subscription_number()

        sub = Subscription(
            user_id=user.id,
            plan=plan.id,
            billing_cycle="one_time",
            price=float(final_price),
            active=False,
            status="PENDING",
            plan_name=plan.name,
            plan_description=plan.description,
            plan_duration_days=plan.duration_days,
            plan_price_paid=final_price,
            plan_currency=currency,
            plan_features=plan.features_json,
            coupon_code=coupon.code if coupon else None,
            discount_amount=discount_amount if discount_amount > 0 else None,
            subscription_number=subscription_number,
            created_at=now,
        )
        session.add(sub)
        await session.flush()

        # Link payment to subscription
        payment.subscription_id = sub.id
        await session.flush()

        # Manual payment (cash): create checkout via provider for instructions
        if payment_method_type == "manual":
            payment.status = "PENDING"
            # Real expiry deadline (REQ 7): owner-configurable per method, default 72h.
            # The client sees a live countdown; after this instant the payment
            # can no longer be submitted and is swept to EXPIRED.
            expires_hours = 72
            if owner_config and owner_config.get("expires_hours"):
                try:
                    expires_hours = int(owner_config["expires_hours"])
                except (TypeError, ValueError):
                    expires_hours = 72
            payment.expired_at = now + timedelta(hours=expires_hours)
            try:
                checkout = await self.provider.create_checkout_session(
                    payment_id=payment.id,
                    amount=final_price,
                    currency=currency,
                    plan_name=plan.name,
                    customer_email=user.email or "",
                    success_url=success_url,
                    cancel_url=cancel_url,
                    metadata={
                        "subscription_id": sub.id,
                        "user_id": user.id,
                        "plan_id": plan.id,
                        "owner_config": owner_config,
                    },
                )

                meta = checkout.metadata
                payment.manual_instructions = meta.get("manual_instructions", "")
                payment.manual_reference = meta.get("manual_reference", "")
                payment.updated_at = datetime.now(timezone.utc)
                await session.flush()

                # Send payment instructions email to client
                if user.email and payment.manual_instructions:
                    await _safe_send(send_manual_payment_instructions_email(
                        to=user.email,
                        first_name=user.first_name or "there",
                        plan_name=plan.name,
                        amount=str(final_price),
                        currency=currency,
                        instructions=payment.manual_instructions,
                        payment_number=payment_number,
                        session=session,
                    ))

                return {
                    "payment_id": payment.id,
                    "payment_number": payment.payment_number,
                    "checkout_url": "",
                    "checkout_id": checkout.checkout_id,
                    "subscription_id": sub.id,
                    "subscription_number": subscription_number,
                    "status": "PENDING",
                    "payment_method_type": "manual",
                    "manual_instructions": payment.manual_instructions,
                    "manual_reference": payment.manual_reference,
                    "expected_amount": float(final_price),
                    "expired_at": payment.expired_at.isoformat() if payment.expired_at else None,
                    "reference_required": bool(owner_config.get("reference_required", True)) if owner_config else True,
                    "owner_config": owner_config,
                }
            except Exception as e:
                logger.exception("Manual payment checkout creation failed")
                raise PaymentServiceError(
                    f"Failed to create manual payment: {e}",
                    status_code=500,
                )

        # Manual crypto payment: create deposit address + expiration
        if payment_method_type == "manual_crypto":
            payment.status = "AWAITING_PAYMENT"
            # The provider (crypto_provider) creates the checkout with deposit address
            try:
                checkout = await self.provider.create_checkout_session(
                    payment_id=payment.id,
                    amount=final_price,
                    currency=currency,
                    plan_name=plan.name,
                    customer_email=user.email or "",
                    success_url=success_url,
                    cancel_url=cancel_url,
                    metadata={
                        "subscription_id": sub.id,
                        "user_id": user.id,
                        "plan_id": plan.id,
                        "owner_config": owner_config,
                    },
                )

                # Extract crypto-specific data from checkout metadata
                meta = checkout.metadata
                payment.deposit_address = meta.get("deposit_address", "")
                payment.deposit_network = meta.get("network", "")
                payment.coin_ticker = meta.get("ticker", "")
                payment.expected_amount = final_price

                # Set expiration: owner-configurable per method (REQ 7),
                # default 60 minutes for crypto.
                expires_hours = 1
                if owner_config and owner_config.get("expires_hours"):
                    try:
                        expires_hours = int(owner_config["expires_hours"])
                    except (TypeError, ValueError):
                        expires_hours = 1
                payment.expired_at = datetime.now(timezone.utc) + timedelta(hours=expires_hours)

                payment.manual_instructions = meta.get("manual_instructions", "")
                payment.manual_reference = meta.get("deposit_address", "")
                payment.updated_at = datetime.now(timezone.utc)
                await session.flush()

                # Send crypto payment instructions email
                if user.email:
                    await _safe_send(send_manual_payment_instructions_email(
                        to=user.email,
                        first_name=user.first_name or "there",
                        plan_name=plan.name,
                        amount=str(final_price),
                        currency=meta.get("ticker", currency),
                        instructions=meta.get("manual_instructions", ""),
                        payment_number=payment_number,
                        session=session,
                    ))

                return {
                    "payment_id": payment.id,
                    "payment_number": payment.payment_number,
                    "checkout_url": "",
                    "checkout_id": checkout.checkout_id,
                    "subscription_id": sub.id,
                    "subscription_number": subscription_number,
                    "status": "AWAITING_PAYMENT",
                    "payment_method_type": "manual_crypto",
                    "deposit_address": payment.deposit_address,
                    "network": payment.deposit_network,
                    "ticker": payment.coin_ticker,
                    "expected_amount": float(final_price),
                    "expired_at": payment.expired_at.isoformat() if payment.expired_at else None,
                    "manual_instructions": payment.manual_instructions,
                    "confirmations_required": meta.get("confirmations_required", 0),
                    "available_networks": meta.get("available_networks", []),
                    "owner_config": owner_config,
                }
            except PaymentProviderError as e:
                payment.status = "FAILED"
                payment.failure_reason = str(e)
                payment.failed_at = datetime.now(timezone.utc)
                payment.updated_at = datetime.now(timezone.utc)
                await session.flush()
                raise PaymentServiceError(
                    f"Crypto provider error: {e}",
                    status_code=502,
                )

        # Automatic payment: create checkout session with provider
        try:
            checkout = await self.provider.create_checkout_session(
                payment_id=payment.id,
                amount=final_price,
                currency=currency,
                plan_name=plan.name,
                customer_email=user.email or "",
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    "subscription_id": sub.id,
                    "user_id": user.id,
                    "plan_id": plan.id,
                },
            )

            payment.provider_checkout_id = checkout.checkout_id
            payment.updated_at = datetime.now(timezone.utc)
            await session.flush()

            return {
                "payment_id": payment.id,
                "payment_number": payment.payment_number,
                "checkout_url": checkout.checkout_url,
                "checkout_id": checkout.checkout_id,
                "subscription_id": sub.id,
                "subscription_number": subscription_number,
                "status": "PENDING",
                "payment_method_type": "automatic",
                "manual_instructions": None,
                "manual_reference": None,
            }
        except PaymentProviderError as e:
            # Payment creation failed — mark as FAILED
            payment.status = "FAILED"
            payment.failure_reason = str(e)
            payment.failed_at = datetime.now(timezone.utc)
            payment.updated_at = datetime.now(timezone.utc)
            await session.flush()
            raise PaymentServiceError(
                f"Payment provider error: {e}",
                status_code=502,
            )

    # ------------------------------------------------------------------
    # Webhook processing (idempotent)
    # ------------------------------------------------------------------
    async def process_webhook(
        self,
        session: AsyncSession,
        *,
        event: WebhookEvent,
    ) -> Optional[dict]:
        """
        Process a verified webhook event.

        Idempotent: duplicate events are safely ignored.
        Returns a summary dict or None if the event was ignored.
        """
        # Check for duplicate event (idempotency)
        if event.event_id:
            existing = await session.execute(
                select(Payment).where(Payment.provider_event_id == event.event_id)
            )
            if existing.scalar_one_or_none():
                logger.info("Webhook event %s already processed — skipping", event.event_id)
                return None

        # Find the payment by provider IDs
        payment = await self._find_payment_by_provider_ids(
            session,
            provider_payment_id=event.provider_payment_id,
            provider_checkout_id=event.provider_checkout_id,
        )
        if not payment:
            logger.warning("Webhook: no matching payment for event %s", event.event_id)
            return None

        # Validate state transition
        if not payment.can_transition_to(event.status):
            logger.warning(
                "Webhook: invalid transition %s → %s for payment %s",
                payment.status, event.status, payment.payment_number,
            )
            return None

        # Apply transition
        now = datetime.now(timezone.utc)
        payment.status = event.status
        payment.updated_at = now
        payment.provider_event_id = event.event_id

        if event.provider_payment_id and not payment.provider_payment_id:
            payment.provider_payment_id = event.provider_payment_id
        if event.payment_method:
            payment.payment_method = event.payment_method
        if event.failure_reason:
            payment.failure_reason = event.failure_reason

        if event.status == "PAID":
            payment.paid_at = now
            await self._activate_subscription(session, payment)
            await self._create_receipt(session, payment)
            await self._record_coupon_redemption(session, payment)
        elif event.status == "FAILED":
            payment.failed_at = now
        elif event.status == "CANCELLED":
            payment.cancelled_at = now
        elif event.status == "REFUNDED":
            payment.refunded_at = now

        await session.flush()

        # Send emails AFTER flush — best-effort, non-blocking.
        try:
            await self._fire_payment_emails(payment, event_status=event.status)
        except Exception as e:
            logger.warning("Email notification failed for payment %s: %s", payment.payment_number, e)

        return {
            "payment_id": payment.id,
            "payment_number": payment.payment_number,
            "status": payment.status,
        }

    # ------------------------------------------------------------------
    # Manual payment confirmation (for admin override or direct confirm)
    # ------------------------------------------------------------------
    async def confirm_payment(
        self,
        session: AsyncSession,
        *,
        payment_id: str,
    ) -> dict:
        """
        Confirm a payment by querying the provider.

        Used for admin manual confirmation or retry.
        """
        payment = await session.get(Payment, payment_id)
        if not payment:
            raise PaymentServiceError("Payment not found", status_code=404)

        if payment.status not in ("PENDING", "PROCESSING"):
            raise PaymentServiceError(
                f"Payment cannot be confirmed in status: {payment.status}",
                status_code=400,
            )

        if not payment.provider_payment_id:
            raise PaymentServiceError(
                "No provider payment ID — cannot confirm",
                status_code=400,
            )

        result = await self.provider.get_payment_status(
            provider_payment_id=payment.provider_payment_id,
        )

        now = datetime.now(timezone.utc)
        payment.status = result.status
        payment.updated_at = now

        if result.payment_method:
            payment.payment_method = result.payment_method

        if result.status == "PAID":
            payment.paid_at = now
            await self._activate_subscription(session, payment)
            await self._create_receipt(session, payment)
            await self._record_coupon_redemption(session, payment)
        elif result.status == "FAILED":
            payment.failed_at = now
            payment.failure_reason = result.failure_reason

        await session.flush()

        # Send emails AFTER flush — best-effort, non-blocking.
        try:
            await self._fire_payment_emails(payment, event_status=result.status)
        except Exception as e:
            logger.warning("Email notification failed for confirmed payment %s: %s", payment.payment_number, e)

        await session.flush()

        return payment.to_dict()

    # ------------------------------------------------------------------
    # Cancel a pending payment
    # ------------------------------------------------------------------
    async def cancel_payment(
        self,
        session: AsyncSession,
        *,
        payment_id: str,
        user_id: str,
    ) -> dict:
        """Cancel a PENDING payment. Only the owning user can cancel."""
        payment = await session.get(Payment, payment_id)
        if not payment:
            raise PaymentServiceError("Payment not found", status_code=404)
        if payment.user_id != user_id:
            raise PaymentServiceError("Access denied", status_code=403)
        if not payment.can_transition_to("CANCELLED"):
            raise PaymentServiceError(
                f"Payment cannot be cancelled in status: {payment.status}",
                status_code=400,
            )

        now = datetime.now(timezone.utc)
        payment.status = "CANCELLED"
        payment.cancelled_at = now
        payment.updated_at = now

        # Also cancel the linked PENDING subscription
        if payment.subscription_id:
            sub = await session.get(Subscription, payment.subscription_id)
            if sub and sub.status == "PENDING":
                sub.status = "CANCELLED"
                sub.active = False

        await session.flush()
        return payment.to_dict()

    # ------------------------------------------------------------------
    # Expire stale manual payments (REQ 7/9)
    # ------------------------------------------------------------------
    async def expire_stale_payments(
        self,
        session: AsyncSession,
        *,
        now: Optional[datetime] = None,
    ) -> int:
        """Expire manual payments whose deadline passed and that were never submitted.

        Only PENDING (created, not submitted) and AWAITING_PAYMENT (crypto,
        not submitted) payments with an expired_at in the past are swept to
        EXPIRED. Payments already under verification (PENDING_VERIFICATION)
        are NOT auto-expired — the owner may still review them.

        Returns the number of payments expired.
        """
        now = now or datetime.now(timezone.utc)
        result = await session.execute(
            select(Payment).where(
                Payment.status.in_(["PENDING", "AWAITING_PAYMENT"]),
                Payment.expired_at.is_not(None),
                Payment.expired_at < now,
            )
        )
        stale = result.scalars().all()
        expired_count = 0
        for payment in stale:
            if payment.can_transition_to("EXPIRED"):
                payment.status = "EXPIRED"
                payment.updated_at = now
                # Cancel the linked PENDING subscription so it cannot linger
                if payment.subscription_id:
                    sub = await session.get(Subscription, payment.subscription_id)
                    if sub and sub.status == "PENDING":
                        sub.status = "CANCELLED"
                        sub.active = False
                expired_count += 1
                logger.info(
                    "Payment %s expired (deadline %s passed)",
                    payment.payment_number, payment.expired_at,
                )
                # Notify the client their payment window closed (best-effort)
                try:
                    if _EMAIL_AVAILABLE:
                        from database.db import async_session_factory
                        async with async_session_factory() as db:
                            row = (await db.execute(
                                select(User.email, User.first_name).where(User.id == payment.user_id)
                            )).first()
                        if row and row[0]:
                            await _safe_send(send_payment_expired_email(
                                to=row[0],
                                first_name=row[1] or "there",
                                payment_number=payment.payment_number,
                                plan_name=payment.plan_name or "Subscription",
                                amount=f"{payment.final_amount} {payment.currency}",
                                currency=payment.currency,
                            ))
                except Exception as e:
                    logger.warning("Expiry email failed for %s: %s", payment.payment_number, e)
        if expired_count:
            await session.flush()
        return expired_count

    # ------------------------------------------------------------------
    # Manual payment: transition to PENDING_VERIFICATION
    # ------------------------------------------------------------------
    async def submit_manual_payment(
        self,
        session: AsyncSession,
        *,
        payment_id: str,
        user_id: str,
        manual_reference: Optional[str] = None,
        manual_proof_url: Optional[str] = None,
        payer_name: Optional[str] = None,
        payer_phone: Optional[str] = None,
        payment_date: Optional[datetime] = None,
        amount_paid: Optional[Decimal] = None,
        client_fields_data: Optional[dict] = None,
    ) -> dict:
        """
        Client submits a manual payment for verification.

        Transitions PENDING → PENDING_VERIFICATION.
        Only the owning user can submit.
        Proof of payment is mandatory server-side (never trust the frontend).
        """
        payment = await session.get(Payment, payment_id)
        if not payment:
            raise PaymentServiceError("Payment not found", status_code=404)
        if payment.user_id != user_id:
            raise PaymentServiceError("Access denied", status_code=403)
        if payment.payment_method_type != "manual":
            raise PaymentServiceError(
                "This payment is not a manual payment",
                status_code=400,
            )
        if not payment.can_transition_to("PENDING_VERIFICATION"):
            raise PaymentServiceError(
                f"Payment cannot be submitted in status: {payment.status}",
                status_code=400,
            )
        # A payment whose deadline passed can never be submitted (REQ 7/8).
        # Mark it EXPIRED so the client sees the real reason instead of a
        # generic error, then require a fresh checkout.
        if payment.expired_at and payment.expired_at < datetime.now(timezone.utc):
            payment.status = "EXPIRED"
            payment.updated_at = datetime.now(timezone.utc)
            await session.flush()
            raise PaymentServiceError(
                "This payment has expired. Please create a new payment.",
                status_code=400,
            )
        if not manual_proof_url:
            raise PaymentServiceError(
                "Proof of payment is required. Upload a JPG, PNG or PDF file.",
                status_code=400,
            )

        # The proof URL must reference a file actually uploaded for THIS
        # payment. Uploaded files are named <payment_number>-<hash>.<ext>;
        # accepting anything else would let a client attach another payment's
        # (or another user's) proof for owner review.
        expected_prefix = f"/api/client/uploads/proofs/{payment.payment_number}-"
        if not manual_proof_url.startswith(expected_prefix):
            raise PaymentServiceError(
                "Invalid proof file. Upload the proof for this payment and use the returned URL.",
                status_code=400,
            )

        now = datetime.now(timezone.utc)
        payment.status = "PENDING_VERIFICATION"
        payment.manual_reference = manual_reference or payment.manual_reference
        payment.manual_proof_url = manual_proof_url or payment.manual_proof_url
        payment.payer_name = payer_name or payment.payer_name
        payment.payer_phone = payer_phone or payment.payer_phone
        payment.payment_date = payment_date or payment.payment_date
        if amount_paid is not None:
            payment.amount_paid = amount_paid
        # Store the owner-defined client field values (configuration-driven).
        if client_fields_data:
            meta = dict(payment.metadata_json or {})
            meta["client_fields_data"] = client_fields_data
            payment.metadata_json = meta
        payment.updated_at = now

        await session.flush()

        # Notify billing/owner that a manual payment needs verification
        try:
            if _EMAIL_AVAILABLE and BILLING_EMAIL:
                client_user = await session.get(User, user_id)
                client_name = "Unknown"
                if client_user:
                    client_name = f"{client_user.first_name or ''} {client_user.last_name or ''}".strip() or client_user.email or "Unknown"
                await _safe_send(send_manual_payment_submitted_email(
                    to=BILLING_EMAIL,
                    client_name=client_name,
                    payment_number=payment.payment_number,
                    plan_name=payment.plan_name or "Subscription",
                    amount=f"{payment.final_amount} {payment.currency}",
                    currency=payment.currency,
                    reference=manual_reference,
                    session=session,
                ))
        except Exception as e:
            logger.warning("Email notification failed for manual submission %s: %s", payment.payment_number, e)

        return payment.to_dict()

    # ------------------------------------------------------------------
    # Manual payment: approve (admin/billing)
    # ------------------------------------------------------------------
    async def approve_manual_payment(
        self,
        session: AsyncSession,
        *,
        payment_id: str,
        approved_by: str,
        internal_notes: Optional[str] = None,
    ) -> dict:
        """
        Admin/billing approves a manual payment.

        Transitions PENDING_VERIFICATION → PAID.
        Activates subscription, creates receipt, records coupon redemption.
        Idempotent: second approval does nothing.
        """
        payment = await session.get(Payment, payment_id)
        if not payment:
            raise PaymentServiceError("Payment not found", status_code=404)
        if payment.status == "PAID":
            # Idempotent: already paid
            return payment.to_dict()
        if not payment.can_transition_to("PAID"):
            raise PaymentServiceError(
                f"Payment cannot be approved in status: {payment.status}",
                status_code=400,
            )

        now = datetime.now(timezone.utc)
        payment.status = "PAID"
        payment.paid_at = now
        payment.approved_by = approved_by
        payment.approved_at = now
        payment.internal_notes = internal_notes or payment.internal_notes
        payment.updated_at = now

        await self._activate_subscription(session, payment)
        await self._create_receipt(session, payment)
        await self._record_coupon_redemption(session, payment)

        await session.flush()

        # Send approval + subscription activated emails to client
        try:
            if _EMAIL_AVAILABLE:
                user_email = None
                user_first_name = "there"
                try:
                    from database.db import async_session_factory
                    async with async_session_factory() as db:
                        result = await db.execute(
                            select(User.email, User.first_name).where(User.id == payment.user_id)
                        )
                        row = result.first()
                        if row and row[0]:
                            user_email = row[0]
                            user_first_name = row[1] or "there"
                except Exception:
                    pass

                if user_email:
                    sub_number = ""
                    end_date_str = ""
                    if payment.subscription_id:
                        try:
                            async with async_session_factory() as db2:
                                sub_result = await db2.execute(
                                    select(Subscription.subscription_number, Subscription.end_date)
                                    .where(Subscription.id == payment.subscription_id)
                                )
                                sub_row = sub_result.first()
                                if sub_row:
                                    sub_number = sub_row[0] or ""
                                    if sub_row[1]:
                                        end_date_str = sub_row[1].strftime("%B %d, %Y")
                        except Exception:
                            pass
                    await _safe_send(send_manual_payment_approved_email(
                        to=user_email,
                        first_name=user_first_name,
                        payment_number=payment.payment_number,
                        plan_name=payment.plan_name or "Subscription",
                        amount=f"{payment.final_amount} {payment.currency}",
                        currency=payment.currency,
                    ))
                    await _safe_send(send_subscription_activated_email(
                        to=user_email,
                        first_name=user_first_name,
                        plan_name=payment.plan_name or "Subscription",
                        subscription_number=sub_number,
                        end_date=end_date_str or None,
                    ))
        except Exception as e:
            logger.warning("Email notification failed for approval %s: %s", payment.payment_number, e)

        return payment.to_dict()

    # ------------------------------------------------------------------
    # Manual payment: reject (admin/billing)
    # ------------------------------------------------------------------
    async def reject_manual_payment(
        self,
        session: AsyncSession,
        *,
        payment_id: str,
        rejection_reason: str,
        rejected_by: str,
    ) -> dict:
        """
        Admin/billing rejects a manual payment.

        Transitions PENDING_VERIFICATION → REJECTED (distinct from FAILED,
        which is a provider/system failure — REQ 17).
        Subscription remains inactive.
        """
        payment = await session.get(Payment, payment_id)
        if not payment:
            raise PaymentServiceError("Payment not found", status_code=404)
        if payment.status == "REJECTED":
            # Idempotent: already rejected
            return payment.to_dict()
        if not payment.can_transition_to("REJECTED"):
            raise PaymentServiceError(
                f"Payment cannot be rejected in status: {payment.status}",
                status_code=400,
            )

        now = datetime.now(timezone.utc)
        payment.status = "REJECTED"
        payment.rejection_reason = rejection_reason
        payment.approved_by = rejected_by  # Track who rejected
        payment.rejected_at = now
        payment.updated_at = now

        await session.flush()

        # Send rejection email to client
        try:
            if _EMAIL_AVAILABLE:
                user_email = None
                user_first_name = "there"
                try:
                    from database.db import async_session_factory
                    async with async_session_factory() as db:
                        result = await db.execute(
                            select(User.email, User.first_name).where(User.id == payment.user_id)
                        )
                        row = result.first()
                        if row and row[0]:
                            user_email = row[0]
                            user_first_name = row[1] or "there"
                except Exception:
                    pass

                if user_email:
                    await _safe_send(send_manual_payment_rejected_email(
                        to=user_email,
                        first_name=user_first_name,
                        payment_number=payment.payment_number,
                        plan_name=payment.plan_name or "Subscription",
                        amount=f"{payment.final_amount} {payment.currency}",
                        currency=payment.currency,
                        reason=rejection_reason,
                    ))
        except Exception as e:
            logger.warning("Email notification failed for rejection %s: %s", payment.payment_number, e)

        return payment.to_dict()

    # ------------------------------------------------------------------
    # Internal: activate subscription after payment
    # ------------------------------------------------------------------
    async def _activate_subscription(
        self,
        session: AsyncSession,
        payment: Payment,
    ) -> None:
        """Activate the subscription linked to a successful payment.

        Also creates/activates the client license — a PAID payment must
        propagate through: PAYMENT → PAID → SUBSCRIPTION ACTIVE → LICENSE ACTIVE.
        """
        if payment.subscription_id:
            sub = await session.get(Subscription, payment.subscription_id)
            if not sub:
                logger.error("No subscription found for payment %s", payment.payment_number)
            elif sub.status == "ACTIVE" and sub.active:
                logger.info("Subscription %s already active — skipping", sub.subscription_number)
            else:
                now = datetime.now(timezone.utc)

                # A user may only have ONE active subscription (uq_active_subscription).
                # If they already have an active one, this payment EXTENDS it (renewal)
                # instead of creating a second active row.
                existing = await session.execute(
                    select(Subscription).where(
                        Subscription.user_id == payment.user_id,
                        Subscription.active.is_(True),
                    )
                )
                active_sub = existing.scalars().first()
                if active_sub and active_sub.id != sub.id:
                    from datetime import timedelta
                    base = active_sub.end_date if (active_sub.end_date and active_sub.end_date > now) else now
                    if payment.plan_duration_days:
                        active_sub.end_date = base + timedelta(days=payment.plan_duration_days)
                    # Close the payment's own pending subscription row so it
                    # cannot later be activated (no second active row).
                    sub.active = False
                    sub.status = "CANCELLED"
                    # Point the payment at the extended subscription so the
                    # receipt and license reference the live period.
                    payment.subscription_id = active_sub.id
                    logger.info(
                        "Extended subscription %s by %s days (payment %s)",
                        active_sub.subscription_number, payment.plan_duration_days,
                        payment.payment_number,
                    )
                else:
                    sub.active = True
                    sub.status = "ACTIVE"
                    sub.start_date = now

                    # Calculate end_date from plan duration
                    if payment.plan_duration_days:
                        from datetime import timedelta
                        sub.end_date = now + timedelta(days=payment.plan_duration_days)

                    logger.info(
                        "Subscription %s activated (payment %s)",
                        sub.subscription_number, payment.payment_number,
                    )

        # License activation is independent of subscription existence —
        # every PAID path must end with an active license.
        await self._activate_license(session, payment)

    # ------------------------------------------------------------------
    # Internal: create/activate license after successful payment
    # ------------------------------------------------------------------
    async def _activate_license(
        self,
        session: AsyncSession,
        payment: Payment,
    ) -> Optional[License]:
        """Create an active license for the user after a successful payment.

        Idempotent: if the user already has an ACTIVE license, nothing is
        created (no duplicate licenses). If the user only has expired or
        non-active licenses, a fresh license is created for the new period.
        """
        existing = await session.execute(
            select(License).where(
                License.user_id == payment.user_id,
                License.status == "active",
            )
        )
        lic = existing.scalar_one_or_none()
        if lic:
            # Renewal: extend the active license to match the (possibly
            # extended) subscription period so coverage never lapses.
            if payment.subscription_id:
                sub = await session.get(Subscription, payment.subscription_id)
                if sub and sub.end_date and (lic.expires_at is None or sub.end_date > lic.expires_at):
                    lic.expires_at = sub.end_date
            logger.info(
                "User %s already has an active license — extending expiry",
                payment.user_id,
            )
            return None

        # max_accounts comes from the plan definition (never hardcoded)
        max_accounts = 1
        if payment.plan_id:
            plan = await session.get(PlanDefinition, payment.plan_id)
            if plan:
                max_accounts = plan.max_accounts or 1

        # License validity mirrors the subscription period
        expires_at = None
        if payment.subscription_id:
            sub = await session.get(Subscription, payment.subscription_id)
            if sub and sub.end_date:
                expires_at = sub.end_date

        from security.license_gen import generate_license_key
        lic = License(
            user_id=payment.user_id,
            license_key=generate_license_key(),
            plan=payment.plan_id or "standard",
            max_accounts=max_accounts,
            expires_at=expires_at,
            status="active",
        )
        session.add(lic)
        await session.flush()
        logger.info(
            "License %s created for user %s (plan=%s, max_accounts=%s, expires=%s)",
            lic.license_key, payment.user_id, lic.plan, max_accounts, expires_at,
        )
        return lic

    # ------------------------------------------------------------------
    # Internal: create receipt after successful payment
    # ------------------------------------------------------------------
    async def _create_receipt(
        self,
        session: AsyncSession,
        payment: Payment,
    ) -> Optional[Receipt]:
        """Create an immutable receipt after successful payment."""
        # Idempotency: check if receipt already exists for this payment
        existing = await session.execute(
            select(Receipt).where(Receipt.payment_id == payment.id)
        )
        if existing.scalar_one_or_none():
            return None

        receipt_number = _generate_receipt_number()
        now = datetime.now(timezone.utc)

        # Get subscription dates
        sub_start = None
        sub_expiration = None
        if payment.subscription_id:
            sub = await session.get(Subscription, payment.subscription_id)
            if sub:
                sub_start = sub.start_date
                sub_expiration = sub.end_date

        receipt = Receipt(
            receipt_number=receipt_number,
            payment_id=payment.id,
            user_id=payment.user_id,
            subscription_id=payment.subscription_id,
            plan_name=payment.plan_name or "",
            plan_duration_days=payment.plan_duration_days,
            original_amount=payment.original_amount,
            discount_amount=payment.discount_amount,
            final_amount=payment.final_amount,
            currency=payment.currency,
            coupon_code=payment.coupon_code,
            payment_method=payment.payment_method or payment.payment_provider,
            payment_status="PAID",
            # Crypto receipt fields
            coin_ticker=payment.coin_ticker,
            deposit_network=payment.deposit_network,
            transaction_hash=payment.transaction_hash,
            expected_amount=payment.expected_amount,
            paid_amount_crypto=payment.proof_amount,
            paid_at=payment.paid_at or now,
            subscription_start=sub_start,
            subscription_expiration=sub_expiration,
            created_at=now,
        )
        session.add(receipt)
        logger.info("Receipt %s created for payment %s", receipt_number, payment.payment_number)
        return receipt

    # ------------------------------------------------------------------
    # Internal: record coupon redemption after payment
    # ------------------------------------------------------------------
    async def _record_coupon_redemption(
        self,
        session: AsyncSession,
        payment: Payment,
    ) -> None:
        """Record coupon redemption after successful payment. Idempotent."""
        if not payment.coupon_id or not payment.discount_amount:
            return

        # Idempotency: check if redemption already exists for this payment
        existing = await session.execute(
            select(CouponRedemption).where(
                CouponRedemption.subscription_id == payment.subscription_id,
                CouponRedemption.coupon_id == payment.coupon_id,
            )
        )
        if existing.scalar_one_or_none():
            return

        coupon = await session.get(Coupon, payment.coupon_id)
        if not coupon:
            return

        now = datetime.now(timezone.utc)
        redemption = CouponRedemption(
            coupon_id=coupon.id,
            user_id=payment.user_id,
            subscription_id=payment.subscription_id,
            original_price=payment.original_amount,
            discount_amount=payment.discount_amount,
            final_price=payment.final_amount,
            currency=payment.currency,
            redeemed_at=now,
        )
        session.add(redemption)

        # Update denormalized coupon stats
        coupon.total_redemptions += 1
        coupon.total_discount_granted += payment.discount_amount

        logger.info(
            "Coupon %s redeemed by user %s (payment %s, discount %s %s)",
            coupon.code, payment.user_id, payment.payment_number,
            payment.discount_amount, payment.currency,
        )

    # ------------------------------------------------------------------
    # Internal: fire payment lifecycle emails (session-free)
    # ------------------------------------------------------------------
    async def _fire_payment_emails(
        self,
        payment: Payment,
        *,
        event_status: str,
    ) -> None:
        """Send appropriate emails for payment state changes.

        This method does NOT query the session.  It uses payment snapshot
        data and passes session=None to email functions so they rely solely
        on env / site-settings without touching the caller's transaction.
        """
        if not _EMAIL_AVAILABLE:
            return

        # Look up user email from a standalone query (outside transaction scope).
        # We create a fresh, short-lived session to avoid polluting the caller's.
        from database.db import async_session_factory
        async with async_session_factory() as db:
            result = await db.execute(
                select(User.email, User.first_name).where(User.id == payment.user_id)
            )
            row = result.first()
        if not row or not row[0]:
            return
        user_email = row[0]
        user_first_name = row[1] or "there"

        if event_status == "PAID":
            await _safe_send(send_payment_success_email(
                to=user_email,
                amount=f"{payment.final_amount} {payment.currency}",
                plan=payment.plan_name or "Subscription",
            ))
            sub_number = ""
            end_date_str = ""
            if payment.subscription_id:
                async with async_session_factory() as db2:
                    sub_result = await db2.execute(
                        select(Subscription.subscription_number, Subscription.end_date)
                        .where(Subscription.id == payment.subscription_id)
                    )
                    sub_row = sub_result.first()
                    if sub_row:
                        sub_number = sub_row[0] or ""
                        if sub_row[1]:
                            end_date_str = sub_row[1].strftime("%B %d, %Y")
            await _safe_send(send_subscription_activated_email(
                to=user_email,
                first_name=user_first_name,
                plan_name=payment.plan_name or "Subscription",
                subscription_number=sub_number,
                end_date=end_date_str or None,
            ))

        elif event_status == "FAILED":
            await _safe_send(send_payment_failed_email(
                to=user_email,
                first_name=user_first_name,
                payment_number=payment.payment_number,
                plan_name=payment.plan_name or "Subscription",
                amount=f"{payment.final_amount} {payment.currency}",
                currency=payment.currency,
                reason=payment.failure_reason,
            ))

    # ------------------------------------------------------------------
    # Internal: find payment by provider IDs
    # ------------------------------------------------------------------
    async def _find_payment_by_provider_ids(
        self,
        session: AsyncSession,
        *,
        provider_payment_id: Optional[str] = None,
        provider_checkout_id: Optional[str] = None,
    ) -> Optional[Payment]:
        """Find a payment by provider payment ID or checkout ID."""
        if provider_payment_id:
            result = await session.execute(
                select(Payment).where(Payment.provider_payment_id == provider_payment_id)
            )
            payment = result.scalar_one_or_none()
            if payment:
                return payment

        if provider_checkout_id:
            result = await session.execute(
                select(Payment).where(Payment.provider_checkout_id == provider_checkout_id)
            )
            payment = result.scalar_one_or_none()
            if payment:
                return payment

        return None

    # ------------------------------------------------------------------
    # Crypto payment: submit proof (client)
    # ------------------------------------------------------------------
    async def submit_crypto_proof(
        self,
        session: AsyncSession,
        *,
        payment_id: str,
        user_id: str,
        tx_hash: str,
        amount_sent: Decimal,
        network: str,
        screenshot_url: Optional[str] = None,
        note: Optional[str] = None,
    ) -> dict:
        """
        Client submits crypto payment proof.

        Transitions AWAITING_PAYMENT → TRANSACTION_DETECTED.
        Only the owning user can submit.
        """
        payment = await session.get(Payment, payment_id)
        if not payment:
            raise PaymentServiceError("Payment not found", status_code=404)
        if payment.user_id != user_id:
            raise PaymentServiceError("Access denied", status_code=403)
        if payment.payment_method_type != "manual_crypto":
            raise PaymentServiceError(
                "This payment is not a crypto payment",
                status_code=400,
            )
        if not payment.can_transition_to("TRANSACTION_DETECTED"):
            raise PaymentServiceError(
                f"Payment cannot be submitted in status: {payment.status}",
                status_code=400,
            )

        now = datetime.now(timezone.utc)
        payment.status = "TRANSACTION_DETECTED"
        payment.proof_tx_hash = tx_hash
        payment.proof_amount = amount_sent
        payment.proof_screenshot_url = screenshot_url
        payment.proof_note = note
        payment.proof_submitted_at = now
        payment.deposit_network = network
        payment.updated_at = now

        await session.flush()

        # Notify billing/owner that a crypto payment needs verification
        try:
            if _EMAIL_AVAILABLE and BILLING_EMAIL:
                client_user = await session.get(User, user_id)
                client_name = "Unknown"
                if client_user:
                    client_name = f"{client_user.first_name or ''} {client_user.last_name or ''}".strip() or client_user.email or "Unknown"
                await _safe_send(send_manual_payment_submitted_email(
                    to=BILLING_EMAIL,
                    client_name=client_name,
                    payment_number=payment.payment_number,
                    plan_name=payment.plan_name or "Subscription",
                    amount=f"{payment.final_amount} {payment.currency}",
                    currency=payment.currency,
                    reference=tx_hash,
                    session=session,
                ))
        except Exception as e:
            logger.warning("Email notification failed for crypto submission %s: %s", payment.payment_number, e)

        return payment.to_dict()

    # ------------------------------------------------------------------
    # Crypto payment: auto-verify and activate (blockchain API confirmed)
    # ------------------------------------------------------------------
    async def auto_verify_crypto_payment(
        self,
        session: AsyncSession,
        *,
        payment_id: str,
        tx_hash: str,
        confirmations: int,
        detected_amount: Decimal,
        sender_address: Optional[str] = None,
    ) -> dict:
        """
        Automatically verify and activate a crypto payment after blockchain
        confirmation.  Called by the blockchain monitoring service when
        confirmations reach the required threshold.

        Transitions CONFIRMING → PAID.
        """
        payment = await session.get(Payment, payment_id)
        if not payment:
            raise PaymentServiceError("Payment not found", status_code=404)
        if payment.status == "PAID":
            return payment.to_dict()  # Idempotent

        if not payment.can_transition_to("PAID"):
            raise PaymentServiceError(
                f"Payment cannot be auto-verified in status: {payment.status}",
                status_code=400,
            )

        now = datetime.now(timezone.utc)
        payment.status = "PAID"
        payment.paid_at = now
        payment.transaction_hash = tx_hash
        payment.confirmation_count = confirmations
        payment.sender_address = sender_address
        payment.detected_at = now
        payment.confirmed_at = now
        payment.verification_type = "automatic"
        payment.updated_at = now

        await self._activate_subscription(session, payment)
        await self._create_receipt(session, payment)
        await self._record_coupon_redemption(session, payment)
        await session.flush()

        try:
            await self._fire_payment_emails(payment, event_status="PAID")
        except Exception as e:
            logger.warning("Email notification failed for crypto auto-verify %s: %s", payment.payment_number, e)

        return payment.to_dict()

    # ------------------------------------------------------------------
    # Crypto payment: manual review approve (owner/billing override)
    # ------------------------------------------------------------------
    async def approve_crypto_manual_review(
        self,
        session: AsyncSession,
        *,
        payment_id: str,
        approved_by: str,
        internal_notes: Optional[str] = None,
        verification_type: str = "owner_override",
    ) -> dict:
        """
        Owner/Billing approves a crypto payment after manual review.

        Works from any of: TRANSACTION_DETECTED, CONFIRMING, MANUAL_REVIEW.
        Transitions to PAID and activates subscription.
        """
        payment = await session.get(Payment, payment_id)
        if not payment:
            raise PaymentServiceError("Payment not found", status_code=404)
        if payment.status == "PAID":
            return payment.to_dict()  # Idempotent

        allowed_statuses = {"TRANSACTION_DETECTED", "CONFIRMING", "MANUAL_REVIEW"}
        if payment.status not in allowed_statuses:
            raise PaymentServiceError(
                f"Payment cannot be approved from status: {payment.status}",
                status_code=400,
            )

        now = datetime.now(timezone.utc)
        payment.status = "PAID"
        payment.paid_at = now
        payment.approved_by = approved_by
        payment.approved_at = now
        payment.verification_type = verification_type
        payment.verified_by = approved_by
        payment.internal_notes = internal_notes or payment.internal_notes
        payment.confirmed_at = now
        payment.updated_at = now

        await self._activate_subscription(session, payment)
        await self._create_receipt(session, payment)
        await self._record_coupon_redemption(session, payment)
        await session.flush()

        try:
            await self._fire_payment_emails(payment, event_status="PAID")
        except Exception as e:
            logger.warning("Email notification failed for crypto manual approve %s: %s", payment.payment_number, e)

        return payment.to_dict()

    # ------------------------------------------------------------------
    # Subscription: suspend (admin/owner)
    # ------------------------------------------------------------------
    async def suspend_subscription(
        self,
        session: AsyncSession,
        *,
        subscription_id: str,
        suspended_by: str,
        reason: str,
    ) -> dict:
        """
        Suspend an active subscription.  Never deletes payment history.

        Creates an audit log entry.  Sends email notification to client.
        """
        sub = await session.get(Subscription, subscription_id)
        if not sub:
            raise PaymentServiceError("Subscription not found", status_code=404)
        if sub.status not in ("ACTIVE",):
            raise PaymentServiceError(
                f"Subscription cannot be suspended in status: {sub.status}",
                status_code=400,
            )

        now = datetime.now(timezone.utc)
        sub.status = "SUSPENDED"
        sub.active = False
        sub.suspension_reason = reason
        sub.suspended_by = suspended_by
        sub.suspended_at = now

        # Log audit event
        await self._log_payment_audit(
            session,
            event_type="subscription.suspended",
            message=f"Subscription {sub.subscription_number or sub.id} suspended: {reason}",
            user_id=suspended_by,
            payload={
                "subscription_id": sub.id,
                "subscription_number": sub.subscription_number,
                "reason": reason,
            },
        )

        await session.flush()

        # Send email notification to client
        try:
            if _EMAIL_AVAILABLE:
                user_email = None
                user_first_name = "there"
                from database.db import async_session_factory
                async with async_session_factory() as db:
                    result = await db.execute(
                        select(User.email, User.first_name).where(User.id == sub.user_id)
                    )
                    row = result.first()
                    if row and row[0]:
                        user_email = row[0]
                        user_first_name = row[1] or "there"
                if user_email:
                    await _safe_send(send_payment_failed_email(
                        to=user_email,
                        first_name=user_first_name,
                        payment_number=sub.subscription_number or sub.id,
                        plan_name=sub.plan_name or "Subscription",
                        amount=f"{sub.plan_price_paid} {sub.plan_currency}" if sub.plan_price_paid else "N/A",
                        currency=sub.plan_currency or "USD",
                        reason=f"Subscription suspended: {reason}",
                    ))
        except Exception as e:
            logger.warning("Email notification failed for subscription suspension %s: %s", sub.subscription_number, e)

        logger.info(
            "Subscription %s suspended by %s: %s",
            sub.subscription_number, suspended_by, reason,
        )
        return {
            "subscription_id": sub.id,
            "subscription_number": sub.subscription_number,
            "status": sub.status,
            "suspended_at": now.isoformat(),
            "reason": reason,
        }

    # ------------------------------------------------------------------
    # Subscription: revoke (owner only)
    # ------------------------------------------------------------------
    async def revoke_subscription(
        self,
        session: AsyncSession,
        *,
        subscription_id: str,
        revoked_by: str,
        reason: str,
    ) -> dict:
        """
        Permanently revoke a subscription.  Never deletes payment history.

        Creates an audit log entry.  Sends email notification to client.
        Owner-only action.
        """
        sub = await session.get(Subscription, subscription_id)
        if not sub:
            raise PaymentServiceError("Subscription not found", status_code=404)
        if sub.status in ("REVOKED",):
            return {
                "subscription_id": sub.id,
                "subscription_number": sub.subscription_number,
                "status": sub.status,
            }  # Idempotent

        now = datetime.now(timezone.utc)
        sub.status = "REVOKED"
        sub.active = False
        sub.revoke_reason = reason
        sub.revoked_by = revoked_by
        sub.revoked_at = now
        sub.end_date = now  # End immediately

        # Log audit event
        await self._log_payment_audit(
            session,
            event_type="subscription.revoked",
            message=f"Subscription {sub.subscription_number or sub.id} revoked: {reason}",
            user_id=revoked_by,
            payload={
                "subscription_id": sub.id,
                "subscription_number": sub.subscription_number,
                "reason": reason,
            },
        )

        await session.flush()

        # Send email notification to client
        try:
            if _EMAIL_AVAILABLE:
                user_email = None
                user_first_name = "there"
                from database.db import async_session_factory
                async with async_session_factory() as db:
                    result = await db.execute(
                        select(User.email, User.first_name).where(User.id == sub.user_id)
                    )
                    row = result.first()
                    if row and row[0]:
                        user_email = row[0]
                        user_first_name = row[1] or "there"
                if user_email:
                    await _safe_send(send_payment_failed_email(
                        to=user_email,
                        first_name=user_first_name,
                        payment_number=sub.subscription_number or sub.id,
                        plan_name=sub.plan_name or "Subscription",
                        amount=f"{sub.plan_price_paid} {sub.plan_currency}" if sub.plan_price_paid else "N/A",
                        currency=sub.plan_currency or "USD",
                        reason=f"Subscription revoked: {reason}",
                    ))
        except Exception as e:
            logger.warning("Email notification failed for subscription revocation %s: %s", sub.subscription_number, e)

        logger.info(
            "Subscription %s revoked by %s: %s",
            sub.subscription_number, revoked_by, reason,
        )
        return {
            "subscription_id": sub.id,
            "subscription_number": sub.subscription_number,
            "status": sub.status,
            "revoked_at": now.isoformat(),
            "reason": reason,
        }

    # ------------------------------------------------------------------
    # Internal: audit log helper
    # ------------------------------------------------------------------
    async def _log_payment_audit(
        self,
        session: AsyncSession,
        *,
        event_type: str,
        message: str,
        user_id: Optional[str] = None,
        payload: Optional[dict] = None,
    ) -> None:
        """Write an entry to the audit_logs table."""
        from database.models import AuditLog
        audit = AuditLog(
            event_type=event_type,
            severity="INFO",
            source="payment_service",
            message=message,
            user_id=user_id,
            payload_json=payload,
        )
        session.add(audit)

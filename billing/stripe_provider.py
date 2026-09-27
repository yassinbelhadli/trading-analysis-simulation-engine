"""
Stripe payment provider adapter.

Implements the PaymentProvider interface for Stripe Checkout Sessions
and webhooks. Uses the stripe Python SDK.

Environment variables:
    PAYMENT_PROVIDER=stripe
    STRIPE_SECRET_KEY=sk_test_... or sk_live_...
    STRIPE_WEBHOOK_SECRET=whsec_...
    STRIPE_PUBLISHABLE_KEY=pk_test_... or pk_live_...
"""
from __future__ import annotations

import json
import logging
import os
from decimal import Decimal
from typing import Optional

from billing.provider import (
    CheckoutSession,
    PaymentProvider,
    PaymentProviderError,
    PaymentResult,
    ProviderState,
    WebhookEvent,
)

logger = logging.getLogger(__name__)


class StripeProvider(PaymentProvider):
    """
    Stripe Checkout Sessions + Webhook adapter.

    This provider is Stripe-ready but requires STRIPE_SECRET_KEY
    to be configured. If not configured, is_configured returns False
    and all operations raise PaymentProviderError.
    """

    def __init__(self):
        self._stripe = None

    def _get_stripe(self):
        """Lazy-import stripe SDK to avoid import errors when not installed."""
        if self._stripe is None:
            try:
                import stripe
                self._stripe = stripe
                secret_key = os.getenv("STRIPE_SECRET_KEY", "")
                if secret_key:
                    stripe.api_key = secret_key
            except ImportError:
                raise PaymentProviderError(
                    "Stripe SDK is not installed. Run: pip install stripe",
                    provider="stripe",
                    code="SDK_MISSING",
                )
        return self._stripe

    @property
    def name(self) -> str:
        return "stripe"

    @property
    def display_name(self) -> str:
        return "Stripe"

    @property
    def state(self) -> ProviderState:
        key = os.getenv("STRIPE_SECRET_KEY", "")
        webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
        if key and webhook_secret:
            return ProviderState.CONFIGURED
        return ProviderState.NOT_CONFIGURED

    @property
    def is_configured(self) -> bool:
        """Stripe is configured only if a secret key is present."""
        return self.state == ProviderState.CONFIGURED

    def supported_currencies(self) -> set[str]:
        """Stripe supports a wide range of currencies."""
        return {"USD", "EUR", "MAD", "GBP", "CAD", "AUD", "CHF", "JPY"}

    def supports_recurring(self) -> bool:
        return True

    async def create_checkout_session(
        self,
        *,
        payment_id: str,
        amount: Decimal,
        currency: str,
        plan_name: str,
        customer_email: str,
        success_url: str,
        cancel_url: str,
        metadata: Optional[dict] = None,
    ) -> CheckoutSession:
        if not self.is_configured:
            raise PaymentProviderError(
                "Stripe is not configured. Set STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET.",
                provider="stripe",
                code="NOT_CONFIGURED",
            )

        stripe = self._get_stripe()

        # Stripe amounts are in smallest currency unit (cents for USD/EUR, centimes for MAD)
        # For simplicity and because Stripe supports decimal amounts for MAD,
        # we pass the amount as a decimal with 2 decimal places.
        amount_cents = int(amount * 100)

        merged_metadata = {
            "payment_id": payment_id,
            **(metadata or {}),
        }

        try:
            session = stripe.checkout.Session.create(
                mode="payment",
                line_items=[
                    {
                        "price_data": {
                            "currency": currency.lower(),
                            "product_data": {
                                "name": f"{plan_name} Subscription",
                            },
                            "unit_amount": amount_cents,
                        },
                        "quantity": 1,
                    }
                ],
                success_url=success_url,
                cancel_url=cancel_url,
                customer_email=customer_email,
                metadata=merged_metadata,
                payment_intent_data={
                    "metadata": merged_metadata,
                },
            )

            return CheckoutSession(
                checkout_id=session.id,
                checkout_url=session.url or "",
                provider="stripe",
                metadata=merged_metadata,
            )
        except Exception as e:
            logger.error("Stripe checkout session creation failed: %s", e)
            raise PaymentProviderError(
                f"Failed to create checkout session: {e}",
                provider="stripe",
                code="CHECKOUT_FAILED",
            )

    async def confirm_payment(
        self,
        *,
        provider_payment_id: str,
    ) -> PaymentResult:
        if not self.is_configured:
            raise PaymentProviderError(
                "Stripe is not configured.",
                provider="stripe",
                code="NOT_CONFIGURED",
            )

        stripe = self._get_stripe()

        try:
            intent = stripe.PaymentIntent.retrieve(provider_payment_id)

            status_map = {
                "succeeded": "PAID",
                "processing": "PROCESSING",
                "requires_payment_method": "PENDING",
                "requires_confirmation": "PENDING",
                "requires_action": "PENDING",
                "canceled": "CANCELLED",
                "requires_capture": "PROCESSING",
            }

            mapped_status = status_map.get(intent.status, "FAILED")

            return PaymentResult(
                success=(intent.status == "succeeded"),
                provider_payment_id=provider_payment_id,
                status=mapped_status,
                payment_method=intent.payment_method_types[0] if intent.payment_method_types else None,
                metadata={"stripe_status": intent.status},
            )
        except Exception as e:
            logger.error("Stripe confirm_payment failed: %s", e)
            return PaymentResult(
                success=False,
                provider_payment_id=provider_payment_id,
                status="FAILED",
                failure_reason=str(e),
            )

    def verify_webhook_signature(
        self,
        *,
        payload: bytes,
        signature: str,
    ) -> bool:
        if not self.is_configured:
            return False

        stripe = self._get_stripe()
        webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")

        try:
            stripe.Webhook.construct_event(
                payload, signature, webhook_secret
            )
            return True
        except (stripe.error.SignatureVerificationError, ValueError) as e:
            logger.warning("Stripe webhook signature verification failed: %s", e)
            return False

    async def parse_webhook_event(
        self,
        *,
        payload: bytes,
        headers: dict,
    ) -> Optional[WebhookEvent]:
        if not self.is_configured:
            return None

        stripe = self._get_stripe()

        # Verify signature first
        sig_header = headers.get("stripe-signature", "")
        if not self.verify_webhook_signature(payload=payload, signature=sig_header):
            logger.warning("Stripe webhook signature invalid — rejecting event")
            return None

        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            logger.error("Stripe webhook: invalid JSON payload")
            return None

        event_type = event.get("type", "")
        event_id = event.get("id", "")
        data_object = event.get("data", {}).get("object", {})

        # Map Stripe event types to our internal status
        if event_type == "checkout.session.completed":
            return WebhookEvent(
                event_id=event_id,
                event_type=event_type,
                provider_payment_id=data_object.get("payment_intent"),
                provider_checkout_id=data_object.get("id"),
                status="PAID",
                amount=Decimal(str(data_object.get("amount_total", 0))) / 100 if data_object.get("amount_total") else None,
                currency=(data_object.get("currency") or "").upper(),
                payment_method=data_object.get("payment_method_types", [None])[0] if data_object.get("payment_method_types") else None,
                metadata=data_object.get("metadata", {}),
                raw=event,
            )
        elif event_type == "payment_intent.succeeded":
            return WebhookEvent(
                event_id=event_id,
                event_type=event_type,
                provider_payment_id=data_object.get("id"),
                status="PAID",
                amount=Decimal(str(data_object.get("amount", 0))) / 100 if data_object.get("amount") else None,
                currency=(data_object.get("currency") or "").upper(),
                payment_method=data_object.get("payment_method_types", [None])[0] if data_object.get("payment_method_types") else None,
                metadata=data_object.get("metadata", {}),
                raw=event,
            )
        elif event_type == "payment_intent.payment_failed":
            return WebhookEvent(
                event_id=event_id,
                event_type=event_type,
                provider_payment_id=data_object.get("id"),
                status="FAILED",
                failure_reason=data_object.get("last_payment_error", {}).get("message"),
                metadata=data_object.get("metadata", {}),
                raw=event,
            )
        elif event_type == "charge.refunded":
            return WebhookEvent(
                event_id=event_id,
                event_type=event_type,
                provider_payment_id=data_object.get("payment_intent"),
                status="REFUNDED",
                amount=Decimal(str(data_object.get("amount_refunded", 0))) / 100 if data_object.get("amount_refunded") else None,
                currency=(data_object.get("currency") or "").upper(),
                metadata=data_object.get("metadata", {}),
                raw=event,
            )
        else:
            logger.info("Stripe webhook: unhandled event type %s", event_type)
            return None

    async def get_payment_status(
        self,
        *,
        provider_payment_id: str,
    ) -> PaymentResult:
        return await self.confirm_payment(provider_payment_id=provider_payment_id)

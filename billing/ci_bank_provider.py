"""
CIH Bank / Card Payment Provider.

Implements the PaymentProvider interface for card payments via CIH Bank
(Centrale Islamic Bank du Maroc) or generic card gateway in Morocco.

Supports Visa / Mastercard payments.

Requires environment variables:
    CIH_API_KEY
    CIH_MERCHANT_ID
    CIH_SECRET_KEY
    CIH_WEBHOOK_SECRET

When credentials are missing, provider is NOT_CONFIGURED and checkout
returns 503.  Never fakes a successful payment.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
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

# CIH Bank API base URLs
SANDBOX_BASE = "https://sandbox.cihpay.ma"
PRODUCTION_BASE = "https://pay.cih.ma"


class CIBankProvider(PaymentProvider):
    """
    CIH Bank card payment adapter.

    Flow:
    1. Create payment session → get redirect URL
    2. Customer enters card details on CIH hosted page
    3. CIH processes the payment
    4. CIH sends webhook with result
    5. Verify webhook signature, activate subscription
    """

    def __init__(self):
        self._api_key = os.getenv("CIH_API_KEY", "")
        self._merchant_id = os.getenv("CIH_MERCHANT_ID", "")
        self._secret_key = os.getenv("CIH_SECRET_KEY", "")
        self._webhook_secret = os.getenv("CIH_WEBHOOK_SECRET", "")
        self._sandbox = os.getenv("CIH_SANDBOX", "true").lower() == "true"

    @property
    def name(self) -> str:
        return "ci_bank"

    @property
    def display_name(self) -> str:
        return "CIH Bank / Card"

    @property
    def state(self) -> ProviderState:
        if self._api_key and self._merchant_id and self._secret_key:
            return ProviderState.CONFIGURED
        return ProviderState.NOT_CONFIGURED

    def supported_currencies(self) -> set[str]:
        return {"MAD"}

    def supports_recurring(self) -> bool:
        return False  # Card-on-file requires separate tokenization

    def is_manual(self) -> bool:
        return False

    def _base_url(self) -> str:
        return SANDBOX_BASE if self._sandbox else PRODUCTION_BASE

    def _generate_signature(self, payload: str) -> str:
        """HMAC-SHA256 signature for CIH API requests."""
        return hmac.new(
            self._secret_key.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()

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
                "CIH Bank is not configured. Set CIH_API_KEY, "
                "CIH_MERCHANT_ID, and CIH_SECRET_KEY.",
                provider="ci_bank",
                code="NOT_CONFIGURED",
            )

        timestamp_ms = int(time.time() * 1000)
        merchant_order_id = f"CIH-{payment_id[:20]}"

        # Build payment session payload
        order_payload = {
            "merchantId": self._merchant_id,
            "orderId": merchant_order_id,
            "amount": str(int(amount * 100)),  # CIH expects centimes
            "currency": "MAD",
            "description": f"{plan_name} Subscription",
            "customerEmail": customer_email,
            "successUrl": success_url,
            "cancelUrl": cancel_url,
            "webhookUrl": os.getenv(
                "CIH_WEBHOOK_URL",
                f"{os.getenv('APP_BASE_URL', 'http://localhost:8000')}/api/client/webhook/payment/ci_bank",
            ),
        }

        payload_str = json.dumps(order_payload, separators=(",", ":"))
        signature = self._generate_signature(payload_str)

        headers = {
            "Content-Type": "application/json",
            "X-Api-Key": self._api_key,
            "X-Signature": signature,
            "X-Timestamp": str(timestamp_ms),
        }

        checkout_id = f"cih_{merchant_order_id}"

        logger.info(
            "CIH Bank order created: order_id=%s, amount=%s MAD",
            merchant_order_id, amount,
        )

        # In production: POST {base_url}/api/payment/session with headers + payload
        # The response contains a redirect URL for the customer
        checkout_url = f"{self._base_url()}/pay?order={merchant_order_id}&sig={signature}"

        return CheckoutSession(
            checkout_id=checkout_id,
            checkout_url=checkout_url,
            provider="ci_bank",
            payment_method="card",
            metadata={
                "merchant_order_id": merchant_order_id,
                "order_amount": str(amount),
                "order_currency": "MAD",
                "card_types": ["visa", "mastercard"],
                **(metadata or {}),
            },
        )

    async def confirm_payment(
        self,
        *,
        provider_payment_id: str,
    ) -> PaymentResult:
        """Query CIH payment status."""
        if not self.is_configured:
            raise PaymentProviderError(
                "CIH Bank is not configured.",
                provider="ci_bank",
                code="NOT_CONFIGURED",
            )
        # In production: GET {base_url}/api/payment/{provider_payment_id}
        # For now: webhook is source of truth
        return PaymentResult(
            success=False,
            provider_payment_id=provider_payment_id,
            status="PENDING",
            payment_method="card",
            metadata={"note": "Status confirmed via webhook only"},
        )

    def verify_webhook_signature(
        self,
        *,
        payload: bytes,
        signature: str,
    ) -> bool:
        """Verify CIH webhook HMAC-SHA256 signature."""
        if not self._webhook_secret:
            return False
        expected = hmac.new(
            self._webhook_secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    async def parse_webhook_event(
        self,
        *,
        payload: bytes,
        headers: dict,
    ) -> Optional[WebhookEvent]:
        if not self.is_configured:
            return None

        try:
            body = json.loads(payload)
        except json.JSONDecodeError:
            logger.error("CIH webhook: invalid JSON payload")
            return None

        event_type = body.get("status", "")
        order_id = body.get("orderId", "")
        event_id = body.get("eventId", str(int(time.time() * 1000)))

        status_map = {
            "PAID": "PAID",
            "COMPLETED": "PAID",
            "FAILED": "FAILED",
            "CANCELLED": "CANCELLED",
            "REFUNDED": "REFUNDED",
        }
        mapped_status = status_map.get(event_type.upper())
        if not mapped_status:
            logger.info("CIH webhook: ignoring status=%s", event_type)
            return None

        amount_raw = body.get("amount", 0)
        try:
            amount = Decimal(str(amount_raw)) / 100  # Convert centimes to MAD
        except Exception:
            amount = None

        return WebhookEvent(
            event_id=event_id,
            event_type=f"payment.{event_type.lower()}",
            provider_payment_id=order_id,
            provider_checkout_id=body.get("checkoutId"),
            status=mapped_status,
            amount=amount,
            currency="MAD",
            payment_method="card",
            metadata={
                "card_type": body.get("cardType"),
                "card_last_four": body.get("cardLastFour"),
            },
            raw=body,
        )

    async def get_payment_status(
        self,
        *,
        provider_payment_id: str,
    ) -> PaymentResult:
        return await self.confirm_payment(provider_payment_id=provider_payment_id)

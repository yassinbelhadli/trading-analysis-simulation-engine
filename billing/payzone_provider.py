"""
Payzone payment provider adapter.

Implements the PaymentProvider interface for Payzone Morocco
(Payment Page API + HMAC webhook verification).

Requires environment variables:
    PAYMENT_PROVIDER=payzone
    PAYZONE_MERCHANT_ACCOUNT=<merchant account name>
    PAYZONE_CALLER_NAME=<API caller name>
    PAYZONE_CALLER_PASSWORD=<API caller password / HMAC secret>
    PAYZONE_PAYWALL_URL=<paywall URL for payment page>
    PAYZONE_SECRET_KEY=<paywall secret key for signature>
    PAYZONE_SANDBOX=false  (set true for sandbox testing)

Official docs:
    http://developers.payzone.ma/
    http://developers.payzone.ma/PaymentPageAPI
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
from decimal import Decimal, InvalidOperation
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

# Payzone API base URLs
SANDBOX_API = "https://payment-sandbox.payzone.ma"
PRODUCTION_API = "https://payment.payzone.ma"


class PayzoneProvider(PaymentProvider):
    """
    Payzone Morocco payment page adapter.

    Flow:
    1. Build payload with order details + HMAC signature
    2. POST form to paywall URL (customer redirected to Payzone payment page)
    3. Customer completes payment on Payzone page
    4. Payzone sends webhook notification with charge status
    5. Verify HMAC signature, update payment status

    Credentials: Merchant Account Name, Caller Name, Paywall Secret Key.
    """

    def __init__(self):
        self._merchant_account = os.getenv("PAYZONE_MERCHANT_ACCOUNT", "")
        self._caller_name = os.getenv("PAYZONE_CALLER_NAME", "")
        self._caller_password = os.getenv("PAYZONE_CALLER_PASSWORD", "")
        self._paywall_url = os.getenv("PAYZONE_PAYWALL_URL", "")
        self._secret_key = os.getenv("PAYZONE_SECRET_KEY", "")
        self._sandbox = os.getenv("PAYZONE_SANDBOX", "false").lower() == "true"

    @property
    def name(self) -> str:
        return "payzone"

    @property
    def display_name(self) -> str:
        return "Payzone"

    @property
    def state(self) -> ProviderState:
        if self._merchant_account and self._secret_key and self._paywall_url:
            return ProviderState.CONFIGURED
        return ProviderState.NOT_CONFIGURED

    def supported_currencies(self) -> set[str]:
        """Payzone supports MAD and other ISO currencies."""
        return {"MAD", "USD", "EUR"}

    def supports_recurring(self) -> bool:
        return True  # Payzone supports recurring payments

    def is_manual(self) -> bool:
        return False

    def _generate_paywall_signature(self, json_payload: str) -> str:
        """
        Generate HMAC-SHA256 signature for Payzone paywall.

        From official docs:
            message = callerName + merchantAccountName + timestamp + request_path + request_body
            signature = hmac_sha256_as_hexadecimal(api_secret, message)
        
        For the payment page:
            signature = sha256(paywallSecretKey + jsonPayload)
        """
        combined = self._secret_key + json_payload
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    def _generate_api_signature(
        self,
        method: str,
        path: str,
        body: str = "",
    ) -> tuple[str, str]:
        """
        Generate HMAC signature for Payzone API Gateway.

        From official docs:
            message = callerName + merchantAccountName + timestamp + request_path + request_body
            signature = hmac_sha256_as_hexadecimal(api_secret, message)
        
        Returns (timestamp, signature).
        """
        timestamp = str(int(time.time()))
        message = self._caller_name + self._merchant_account + timestamp + path + body
        signature = hmac.new(
            self._caller_password.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return timestamp, signature

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
                "Payzone is not configured. Set PAYZONE_MERCHANT_ACCOUNT, "
                "PAYZONE_SECRET_KEY, and PAYZONE_PAYWALL_URL.",
                provider="payzone",
                code="NOT_CONFIGURED",
            )

        # Build Payzone payment page payload
        timestamp = int(time.time())
        charge_id = f"PZ-{payment_id[:20]}"

        payload = {
            "merchantAccount": self._merchant_account,
            "timestamp": timestamp,
            "skin": "vps-1-vue",
            "customerId": customer_email or f"user_{payment_id[:12]}",
            "customerCountry": "MA",
            "customerLocale": "en_US",
            "chargeId": charge_id,
            "orderId": payment_id[:32],
            "price": str(amount),
            "currency": currency.upper(),
            "description": f"{plan_name} Subscription",
            "mode": "DEEP_LINK",
            "paymentMethod": "CREDIT_CARD",
            "showPaymentProfiles": False,
            "callbackUrl": os.getenv(
                "PAYZONE_CALLBACK_URL",
                f"{os.getenv('APP_BASE_URL', 'http://localhost:8000')}/api/client/webhook/payment/payzone",
            ),
            "successUrl": success_url,
            "failureUrl": cancel_url,
            "cancelUrl": cancel_url,
        }

        # Generate signature
        json_payload = json.dumps(payload, separators=(",", ":"))
        signature = self._generate_paywall_signature(json_payload)

        logger.info(
            "Payzone checkout created: charge_id=%s, amount=%s %s",
            charge_id, amount, currency,
        )

        # The checkout_url is the paywall URL.
        # Frontend will POST { payload, signature } to this URL via a form.
        return CheckoutSession(
            checkout_id=charge_id,
            checkout_url=self._paywall_url,
            provider="payzone",
            payment_method="credit_card",
            metadata={
                "payload": json_payload,
                "signature": signature,
                "charge_id": charge_id,
                "paywall_url": self._paywall_url,
                **(metadata or {}),
            },
        )

    async def confirm_payment(
        self,
        *,
        provider_payment_id: str,
    ) -> PaymentResult:
        """Query Payzone transaction status via API Gateway."""
        if not self.is_configured:
            raise PaymentProviderError(
                "Payzone is not configured.",
                provider="payzone",
                code="NOT_CONFIGURED",
            )

        # NOTE: In production, call:
        # GET {api}/api/v3/charges/{id}
        # with HMAC authentication headers
        # For now, return unknown status — webhook is source of truth.

        return PaymentResult(
            success=False,
            provider_payment_id=provider_payment_id,
            status="PENDING",
            payment_method="credit_card",
            metadata={"note": "Status confirmed via webhook only"},
        )

    def verify_webhook_signature(
        self,
        *,
        payload: bytes,
        signature: str,
    ) -> bool:
        """
        Verify Payzone webhook (callback notification) signature.

        Payzone uses HMAC-SHA256 for callback verification.
        The notification includes a signature in the request.
        """
        if not self.is_configured:
            return False

        # Payzone callback notifications include a signature
        # that we verify against our secret key
        try:
            expected = hashlib.sha256(
                (self._secret_key + payload.decode("utf-8")).encode("utf-8")
            ).hexdigest()
            return hmac.compare_digest(expected, signature)
        except Exception as e:
            logger.warning("Payzone webhook signature verification failed: %s", e)
            return False

    async def parse_webhook_event(
        self,
        *,
        payload: bytes,
        headers: dict,
    ) -> Optional[WebhookEvent]:
        """
        Parse Payzone callback notification.

        From official docs, the callback includes:
        - id: transaction ID
        - orderId: merchant order ID
        - status: CHARGED, DECLINED, CANCELLED, ERROR, etc.
        - merchantAccount: merchant account name
        - lineItem: { amount, currency, description }
        """
        if not self.is_configured:
            return None

        try:
            body = json.loads(payload)
        except json.JSONDecodeError:
            logger.error("Payzone webhook: invalid JSON payload")
            return None

        # Extract payment ID from orderId (our payment_id)
        order_id = body.get("orderId", "")
        internal_id = body.get("internalId", "")
        status = body.get("status", "")
        charge_id = body.get("id", "")

        # Map Payzone status to our internal status
        status_map = {
            "CHARGED": "PAID",
            "AUTHORIZED": "PAID",
            "CANCELLED": "CANCELLED",
            "DECLINED": "FAILED",
            "ERROR": "FAILED",
            "CHARGED_BACK": "REFUNDED",
            "REFUNDED": "REFUNDED",
        }
        mapped_status = status_map.get(status, None)

        if mapped_status is None:
            logger.info("Payzone webhook: ignoring status=%s", status)
            return None

        # Extract amount from lineItem
        amount_raw = body.get("lineItem", {}).get("amount", 0)
        try:
            amount = Decimal(str(amount_raw))
        except (InvalidOperation, ValueError):
            amount = None

        return WebhookEvent(
            event_id=charge_id or order_id,
            event_type=f"charge.{status.lower()}",
            provider_payment_id=order_id,
            provider_checkout_id=charge_id,
            status=mapped_status,
            amount=amount,
            currency=(body.get("lineItem", {}).get("currency") or "").upper(),
            payment_method="credit_card",
            metadata={
                "payzone_status": status,
                "internal_id": internal_id,
            },
            raw=body,
        )

    async def get_payment_status(
        self,
        *,
        provider_payment_id: str,
    ) -> PaymentResult:
        return await self.confirm_payment(provider_payment_id=provider_payment_id)

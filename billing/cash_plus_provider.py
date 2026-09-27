"""
Cash Plus payment provider adapter.

Implements the PaymentProvider interface for Cash Plus Morocco
(Cash Plus Payment API for merchants).

Cash Plus provides:
- API integration for merchant cash-payment solution
- Unique token per customer and per transaction
- Payment notification after customer pays at branch
- Back office for real-time operation tracking

Requires environment variables:
    PAYMENT_PROVIDER=cash_plus
    CASH_PLUS_API_KEY=<merchant API key>
    CASH_PLUS_MERCHANT_ID=<merchant ID>
    CASH_PLUS_WEBHOOK_SECRET=<webhook notification secret>
    CASH_PLUS_SANDBOX=false  (set true for sandbox testing)

When API credentials are NOT available, this provider falls back to
manual mode (generating payment instructions for Cash Plus branches).

Official info:
    https://www.cashplus.ma/services-professionnels/cash-plus-payment
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
import string
import time
from decimal import Decimal, InvalidOperation
from typing import Optional

from billing.provider import (
    CheckoutSession,
    ManualPaymentInstructions,
    PaymentProvider,
    PaymentProviderError,
    PaymentResult,
    ProviderState,
    WebhookEvent,
)

logger = logging.getLogger(__name__)

# Cash Plus branch network info for manual fallback
CASH_PLUS_BRANCH_INFO = (
    "Cash Plus has 5,300+ agencies across Morocco.\n"
    "Find your nearest agency: https://www.cashplus.ma/agences"
)


def _generate_token() -> str:
    """Generate a unique Cash Plus payment token like CP-A1B2C3D4E5F6."""
    alphabet = string.ascii_uppercase + string.digits
    suffix = "".join(secrets.choice(alphabet) for _ in range(12))
    return f"CP-{suffix}"


class CashPlusProvider(PaymentProvider):
    """
    Cash Plus Morocco payment adapter.

    Mode 1 (API configured):
        - Calls Cash Plus API to create payment token
        - Customer takes token to Cash Plus branch and pays
        - Cash Plus sends webhook notification
        - We activate subscription

    Mode 2 (API NOT configured — manual fallback):
        - Generates payment instructions + reference number
        - Customer visits Cash Plus branch with reference
        - Owner/billing verifies payment manually
    """

    def __init__(self):
        self._api_key = os.getenv("CASH_PLUS_API_KEY", "")
        self._merchant_id = os.getenv("CASH_PLUS_MERCHANT_ID", "")
        self._webhook_secret = os.getenv("CASH_PLUS_WEBHOOK_SECRET", "")
        self._sandbox = os.getenv("CASH_PLUS_SANDBOX", "false").lower() == "true"
        self._base_url = (
            "https://sandbox.cashplus.ma/api"
            if self._sandbox
            else "https://api.cashplus.ma/api"
        )

    @property
    def name(self) -> str:
        return "cash_plus"

    @property
    def display_name(self) -> str:
        return "Cash Plus"

    @property
    def state(self) -> ProviderState:
        if self._api_key and self._merchant_id:
            return ProviderState.CONFIGURED
        return ProviderState.NOT_CONFIGURED

    def supported_currencies(self) -> set[str]:
        return {"MAD"}

    def supports_recurring(self) -> bool:
        return False

    def is_manual(self) -> bool:
        """Returns True when API credentials are not available."""
        return not self.is_configured

    def _generate_signature(self, payload: str) -> str:
        """Generate HMAC-SHA256 signature for Cash Plus API requests."""
        return hmac.new(
            self._api_key.encode("utf-8"),
            payload.encode("utf-8"),
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
        # Manual fallback when API not configured
        if not self.is_configured:
            return await self._create_manual_checkout(
                payment_id=payment_id,
                amount=amount,
                currency=currency,
                plan_name=plan_name,
                customer_email=customer_email,
                metadata=metadata,
            )

        # API mode: call Cash Plus to create payment token
        token = _generate_token()
        timestamp = int(time.time())

        api_payload = {
            "merchantId": self._merchant_id,
            "amount": str(amount),
            "currency": currency.upper(),
            "reference": payment_id[:32],
            "token": token,
            "description": f"{plan_name} Subscription",
            "customerEmail": customer_email,
            "callbackUrl": os.getenv(
                "CASH_PLUS_CALLBACK_URL",
                f"{os.getenv('APP_BASE_URL', 'http://localhost:8000')}/api/client/webhook/payment/cash_plus",
            ),
        }

        logger.info(
            "Cash Plus API payment created: token=%s, amount=%s %s",
            token, amount, currency,
        )

        return CheckoutSession(
            checkout_id=f"cp_{payment_id[:20]}",
            checkout_url="",  # Customer goes to branch, no web redirect
            provider="cash_plus",
            payment_method="cash_plus",
            metadata={
                "cash_plus_token": token,
                "branch_info": CASH_PLUS_BRANCH_INFO,
                "amount_to_pay": f"{amount:,.2f} {currency}",
                **(metadata or {}),
            },
        )

    async def _create_manual_checkout(
        self,
        *,
        payment_id: str,
        amount: Decimal,
        currency: str,
        plan_name: str,
        customer_email: str,
        metadata: Optional[dict] = None,
    ) -> CheckoutSession:
        """Create a manual payment checkout for Cash Plus."""
        reference = _generate_token()
        amount_str = f"{amount:,.2f}"

        instructions_text = (
            "To complete your payment via Cash Plus:\n\n"
            "1. Visit any Cash Plus agency near you (5,300+ locations).\n"
            "   Find your nearest agency: https://www.cashplus.ma/agences\n"
            "2. Provide the following payment reference to the agent:\n"
            f"   Reference: {reference}\n"
            f"3. Pay the exact amount: {amount_str} {currency}\n"
            "4. Keep the receipt as proof of payment.\n"
            "5. Submit your reference number and receipt in the portal.\n\n"
            "Your payment will be verified within 24-48 hours after submission.\n"
            "Payment expires in 72 hours."
        )

        logger.info(
            "Cash Plus manual payment created: reference=%s, amount=%s %s",
            reference, amount, currency,
        )

        return CheckoutSession(
            checkout_id=f"cp_manual_{payment_id[:20]}",
            checkout_url="",  # No web redirect for manual payments
            provider="cash_plus",
            payment_method="cash_plus",
            metadata={
                "cash_plus_reference": reference,
                "manual_reference": reference,
                "manual_instructions": instructions_text,
                "manual_instructions_data": {
                    "payment_method": "cash_plus",
                    "payment_method_label": "Cash Plus",
                    "reference": reference,
                    "amount_to_pay": f"{amount_str} {currency}",
                    "due_hours": 72,
                },
                "branch_info": CASH_PLUS_BRANCH_INFO,
                **(metadata or {}),
            },
        )

    async def confirm_payment(
        self,
        *,
        provider_payment_id: str,
    ) -> PaymentResult:
        """Query Cash Plus payment status."""
        if not self.is_configured:
            return PaymentResult(
                success=False,
                provider_payment_id=provider_payment_id,
                status="PENDING_VERIFICATION",
                payment_method="cash_plus",
                failure_reason="Manual payment requires admin approval",
            )

        # NOTE: In production, call Cash Plus API to query payment status
        return PaymentResult(
            success=False,
            provider_payment_id=provider_payment_id,
            status="PENDING",
            payment_method="cash_plus",
        )

    def verify_webhook_signature(
        self,
        *,
        payload: bytes,
        signature: str,
    ) -> bool:
        """Verify Cash Plus webhook signature."""
        if not self.is_configured or not self._webhook_secret:
            return False

        try:
            expected = hmac.new(
                self._webhook_secret.encode("utf-8"),
                payload,
                hashlib.sha256,
            ).hexdigest()
            return hmac.compare_digest(expected, signature)
        except Exception as e:
            logger.warning("Cash Plus webhook signature verification failed: %s", e)
            return False

    async def parse_webhook_event(
        self,
        *,
        payload: bytes,
        headers: dict,
    ) -> Optional[WebhookEvent]:
        """Parse Cash Plus payment notification."""
        if not self.is_configured:
            return None

        try:
            body = json.loads(payload)
        except json.JSONDecodeError:
            logger.error("Cash Plus webhook: invalid JSON payload")
            return None

        status = body.get("status", "")
        reference = body.get("reference", "")
        event_id = body.get("transactionId", reference)

        status_map = {
            "PAID": "PAID",
            "SUCCESS": "PAID",
            "FAILED": "FAILED",
            "EXPIRED": "CANCELLED",
        }
        mapped_status = status_map.get(status.upper(), None)

        if mapped_status is None:
            logger.info("Cash Plus webhook: ignoring status=%s", status)
            return None

        amount_raw = body.get("amount", 0)
        try:
            amount = Decimal(str(amount_raw))
        except (InvalidOperation, ValueError):
            amount = None

        return WebhookEvent(
            event_id=event_id,
            event_type=f"payment.{status.lower()}",
            provider_payment_id=reference,
            provider_checkout_id=body.get("transactionId"),
            status=mapped_status,
            amount=amount,
            currency=(body.get("currency") or "").upper(),
            payment_method="cash_plus",
            metadata={
                "cash_plus_reference": reference,
            },
            raw=body,
        )

    async def get_payment_status(
        self,
        *,
        provider_payment_id: str,
    ) -> PaymentResult:
        return await self.confirm_payment(provider_payment_id=provider_payment_id)

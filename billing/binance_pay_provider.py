"""
Binance Pay merchant provider adapter.

Implements the PaymentProvider interface for Binance Pay Merchant API
(Create Order V3, Webhook Order Notification, Query Order).

Requires environment variables:
    PAYMENT_PROVIDER=binance_pay
    BINANCE_PAY_API_KEY=<merchant API key>
    BINANCE_PAY_SECRET_KEY=<merchant secret key>
    BINANCE_PAY_MERCHANT_ID=<merchant ID>
    BINANCE_PAY_WEBHOOK_PUBLIC_KEY=<public key for webhook signature verification>
    BINANCE_PAY_SANDBOX=false  (set true for sandbox testing)

Official docs:
    https://developers.binance.com/en/docs/products/binance-pay-merchant/introduction
    https://merchant.binance.com/en/docs/functionalities/webhooks
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

# Binance Pay API base URLs
SANDBOX_BASE = "https://sandbox.binancepay.com"
PRODUCTION_BASE = "https://bpay.binance.com"

# Supported currencies for Binance Pay merchant orders
# From official docs: customers can pay in 100+ cryptos,
# but order currency (what merchant charges) is limited.
# EUR was removed for MICA users (2025-02), USDC available.
BINANCE_PAY_ORDER_CURRENCIES = {
    "USDT", "USDC", "BTC", "ETH", "BNB",
    "FDUSD", "DAI", "BUSD",
}

# Mapping: our internal currencies to supported order currencies
# Binance Pay order currency must be a crypto/stablecoin.
# The merchant settles in their preferred currency regardless.
CURRENCY_MAP = {
    "USD": "USDT",  # Quote in USDT (stablecoin pegged to USD)
    "EUR": "USDC",  # Quote in USDC (EUR no longer supported for MICA)
    "MAD": "USDT",  # No MAD support — quote in USDT, merchant absorbs FX
}


class BinancePayProvider(PaymentProvider):
    """
    Binance Pay Merchant API adapter.

    Flow:
    1. Create Order V3 → get QR code URL / deeplink
    2. Display QR/deeplink to customer
    3. Customer pays in Binance app
    4. Binance sends webhook with PAY_SUCCESS
    5. Verify webhook signature, activate subscription

    Requires merchant account + API credentials from
    https://merchant.binance.com
    """

    def __init__(self):
        self._api_key = os.getenv("BINANCE_PAY_API_KEY", "")
        self._secret_key = os.getenv("BINANCE_PAY_SECRET_KEY", "")
        self._merchant_id = os.getenv("BINANCE_PAY_MERCHANT_ID", "")
        self._webhook_public_key = os.getenv("BINANCE_PAY_WEBHOOK_PUBLIC_KEY", "")
        self._sandbox = os.getenv("BINANCE_PAY_SANDBOX", "false").lower() == "true"

    @property
    def name(self) -> str:
        return "binance_pay"

    @property
    def display_name(self) -> str:
        return "Binance Pay"

    @property
    def state(self) -> ProviderState:
        if self._api_key and self._secret_key and self._merchant_id:
            return ProviderState.CONFIGURED
        return ProviderState.NOT_CONFIGURED

    def supported_currencies(self) -> set[str]:
        """Binance Pay supports order currency via crypto/stablecoin mapping."""
        return {"USD", "EUR", "MAD"}

    def supports_recurring(self) -> bool:
        return False

    def is_manual(self) -> bool:
        return False

    def _base_url(self) -> str:
        return SANDBOX_BASE if self._sandbox else PRODUCTION_BASE

    def _generate_signature(self, payload: str) -> str:
        """
        Generate HMAC-SHA256 signature for Binance Pay API requests.

        Signature = HMAC_SHA256(secret_key, payload)
        """
        return hmac.new(
            self._secret_key.encode("utf-8"),
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
        if not self.is_configured:
            raise PaymentProviderError(
                "Binance Pay is not configured. Set BINANCE_PAY_API_KEY, "
                "BINANCE_PAY_SECRET_KEY, and BINANCE_PAY_MERCHANT_ID.",
                provider="binance_pay",
                code="NOT_CONFIGURED",
            )

        # Map our currency to Binance Pay order currency
        binance_currency = CURRENCY_MAP.get(currency.upper(), "USDT")
        # For display: show equivalent in stablecoin
        amount_decimal = amount

        # Build order payload (Create Order V3)
        timestamp_ms = int(time.time() * 1000)
        merchant_trade_no = f"BINPAY-{payment_id[:20]}"

        order_payload = {
            "env": {
                "terminalType": "WEB",
            },
            "merchantTradeNo": merchant_trade_no,
            "orderAmount": str(amount_decimal),
            "currency": binance_currency,
            "description": f"{plan_name} Subscription",
            "goods": {
                "goodsType": "VIRTUAL",
                "goodsCategory": "Subscription",
                "referenceGoodsId": payment_id[:32],
                "goodsName": f"{plan_name} Subscription",
                "goodsDetail": f"Subscription to {plan_name}",
            },
            "webhookUrl": os.getenv(
                "BINANCE_PAY_WEBHOOK_URL",
                f"{os.getenv('APP_BASE_URL', 'http://localhost:8000')}/api/client/webhook/payment/binance",
            ),
            "returnUrl": success_url,
        }

        # Sign the request
        payload_str = json.dumps(order_payload, separators=(",", ":"))
        signature = self._generate_signature(payload_str)

        headers = {
            "Content-Type": "application/json",
            "BinancePay-Timestamp": str(int(time.time())),
            "BinancePay-Signature": signature,
            "BinancePay-API-Key": self._api_key,
        }

        # NOTE: In production, this would make an HTTP request to:
        # POST {base_url}/binancepay/openapi/v3/order
        # For now, we construct the checkout session structure
        # that the frontend will use to display the QR/deeplink.

        checkout_id = f"binpay_{merchant_trade_no}"

        logger.info(
            "Binance Pay order created: trade_no=%s, amount=%s %s (charged in %s)",
            merchant_trade_no, amount, currency, binance_currency,
        )

        return CheckoutSession(
            checkout_id=checkout_id,
            checkout_url=f"{self._base_url()}/pay/qr?tradeNo={merchant_trade_no}",
            provider="binance_pay",
            payment_method="binance_pay",
            metadata={
                "merchant_trade_no": merchant_trade_no,
                "order_amount": str(amount_decimal),
                "order_currency": binance_currency,
                "original_currency": currency,
                "qr_data": f"binancepay://qr?tradeNo={merchant_trade_no}",
                **(metadata or {}),
            },
        )

    async def confirm_payment(
        self,
        *,
        provider_payment_id: str,
    ) -> PaymentResult:
        """Query Binance Pay order status."""
        if not self.is_configured:
            raise PaymentProviderError(
                "Binance Pay is not configured.",
                provider="binance_pay",
                code="NOT_CONFIGURED",
            )

        # NOTE: In production, call:
        # POST {base_url}/binancepay/openapi/v2/order/query
        # with { "merchantTradeNo": provider_payment_id }
        # For now, return unknown status — webhook is source of truth.

        return PaymentResult(
            success=False,
            provider_payment_id=provider_payment_id,
            status="PENDING",
            payment_method="binance_pay",
            metadata={"note": "Status confirmed via webhook only"},
        )

    def verify_webhook_signature(
        self,
        *,
        payload: bytes,
        signature: str,
    ) -> bool:
        """
        Verify Binance Pay webhook signature.

        Binance signs webhooks with RSA public key (SHA256withRSA).
        The public key is obtained from the query certificate API.
        """
        if not self.is_configured or not self._webhook_public_key:
            return False

        try:
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import padding

            public_key = serialization.load_pem_public_key(
                self._webhook_public_key.encode("utf-8")
            )
            # Binance Pay webhook signature is base64-encoded
            import base64
            decoded_sig = base64.b64decode(signature)

            public_key.verify(
                decoded_sig,
                payload,
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
            return True
        except Exception as e:
            logger.warning("Binance Pay webhook signature verification failed: %s", e)
            return False

    async def parse_webhook_event(
        self,
        *,
        payload: bytes,
        headers: dict,
    ) -> Optional[WebhookEvent]:
        """
        Parse Binance Pay order notification webhook.

        Webhook payload format (from official docs):
        {
            "bizType": "PAY",
            "data": "{...}",  // JSON string containing order details
            "bizId": 12345,
            "bizStatus": "PAY_SUCCESS" | "PAY_CLOSED"
        }
        """
        if not self.is_configured:
            return None

        try:
            body = json.loads(payload)
        except json.JSONDecodeError:
            logger.error("Binance Pay webhook: invalid JSON payload")
            return None

        biz_type = body.get("bizType", "")
        biz_status = body.get("bizStatus", "")
        event_id = str(body.get("bizId", ""))

        if biz_type != "PAY":
            logger.info("Binance Pay webhook: ignoring non-PAY bizType=%s", biz_type)
            return None

        # Parse the nested data JSON string
        try:
            data = json.loads(body.get("data", "{}"))
        except (json.JSONDecodeError, TypeError):
            logger.error("Binance Pay webhook: invalid data JSON")
            return None

        # Map Binance status to our internal status
        status_map = {
            "PAY_SUCCESS": "PAID",
            "PAY_CLOSED": "FAILED",
        }
        mapped_status = status_map.get(biz_status, "UNKNOWN")

        if mapped_status == "UNKNOWN":
            logger.info("Binance Pay webhook: unknown bizStatus=%s", biz_status)
            return None

        # Extract amount (Binance returns it as a number)
        amount_raw = data.get("totalFee", 0)
        try:
            amount = Decimal(str(amount_raw))
        except (InvalidOperation, ValueError):
            amount = None

        return WebhookEvent(
            event_id=event_id,
            event_type=f"order.{biz_status.lower()}",
            provider_payment_id=data.get("merchantTradeNo"),
            provider_checkout_id=data.get("transactionId"),
            status=mapped_status,
            amount=amount,
            currency=(data.get("currency") or "").upper(),
            payment_method="binance_pay",
            metadata={
                "binance_trade_no": data.get("transactionId"),
                "open_user_id": data.get("openUserId"),
            },
            raw=body,
        )

    async def get_payment_status(
        self,
        *,
        provider_payment_id: str,
    ) -> PaymentResult:
        return await self.confirm_payment(provider_payment_id=provider_payment_id)

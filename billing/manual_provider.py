"""
Manual payment provider adapter.

Handles payments that require manual customer action (paying at a physical
branch): Wafa Cash and Cash Plus (when API credentials are not available).

This provider always returns checkout_url="" and provides manual payment
instructions.  The actual payment is confirmed by an admin/billing user
via the approve_manual_payment() flow.
"""
from __future__ import annotations

import logging
import secrets
import string
from decimal import Decimal
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


def _generate_manual_reference(prefix: str = "MAN") -> str:
    """Generate a unique manual payment reference like MAN-A1B2C3D4."""
    alphabet = string.ascii_uppercase + string.digits
    suffix = "".join(secrets.choice(alphabet) for _ in range(8))
    return f"{prefix}-{suffix}"


# ---------------------------------------------------------------------------
# Manual method configurations
# ---------------------------------------------------------------------------
MANUAL_METHODS = {
    "cash_plus": {
        "name": "cash_plus",
        "display_name": "Cash Plus",
        "supported_currencies": {"MAD"},
        "instructions_template": (
            "To complete your payment via Cash Plus:\n\n"
            "1. Visit any Cash Plus agency near you (5,300+ locations across Morocco).\n"
            "2. Provide the following payment reference to the agent:\n"
            "   Reference: {reference}\n"
            "3. Pay the exact amount: {amount} {currency}\n"
            "4. Keep the receipt as proof of payment.\n"
            "5. Submit your reference number and receipt in the portal.\n\n"
            "Your payment will be verified within 24-48 hours after submission.\n"
            "Payment expires in {due_hours} hours."
        ),
        "due_hours": 72,
    },
    "wafa_cash": {
        "name": "wafa_cash",
        "display_name": "Wafa Cash",
        "supported_currencies": {"MAD"},
        "instructions_template": (
            "To complete your payment via Wafa Cash:\n\n"
            "1. Visit any Wafa Cash point of sale near you.\n"
            "2. Provide the following payment reference to the agent:\n"
            "   Reference: {reference}\n"
            "3. Pay the exact amount: {amount} {currency}\n"
            "4. Keep the receipt as proof of payment.\n"
            "5. Submit your reference number and receipt in the portal.\n\n"
            "Your payment will be verified within 24-48 hours after submission.\n"
            "Payment expires in {due_hours} hours."
        ),
        "due_hours": 72,
    },
    "cih_bank": {
        "name": "cih_bank",
        "display_name": "CIH Bank Transfer",
        "supported_currencies": {"MAD"},
        "instructions_template": (
            "To complete your payment via CIH Bank Transfer:\n\n"
            "1. Transfer the exact amount from your bank account.\n"
            "2. Use the following payment reference:\n"
            "   Reference: {reference}\n"
            "3. Pay the exact amount: {amount} {currency}\n"
            "4. Keep the transfer receipt as proof of payment.\n"
            "5. Submit your reference number and receipt in the portal.\n\n"
            "Your payment will be verified within 24-48 hours after submission.\n"
            "Payment expires in {due_hours} hours."
        ),
        "due_hours": 72,
    },
}


class ManualPaymentProvider(PaymentProvider):
    """
    Provider for manual cash payments (Wafa Cash, Cash Plus fallback).

    This provider:
    - Returns checkout_url="" (no redirect needed)
    - Provides payment instructions via metadata
    - Waits for admin/billing approval to confirm payment
    - Does NOT handle webhooks (manual verification)
    """

    def __init__(self, method: str = "wafa_cash"):
        # Owner-created methods (configuration-driven, e.g. "inwi_money") are
        # NOT in MANUAL_METHODS. They are fully supported: the checkout route
        # passes the owner config through metadata["owner_config"], and
        # _build_owner_instructions() renders the owner's own instructions.
        # The generic config only supplies a display name fallback and the
        # currency set used for validation.
        if method not in MANUAL_METHODS:
            self._method = method
            self._config = {
                "name": method,
                "display_name": method.replace("_", " ").title(),
                "supported_currencies": {"MAD", "USD", "EUR"},
                "instructions_template": (
                    "Complete your {method} payment:\n\n"
                    "1. Follow the payment instructions shown in the portal.\n"
                    "2. Reference: {reference}\n"
                    "3. Pay the exact amount: {amount} {currency}\n"
                    "4. Keep the receipt as proof of payment.\n"
                    "5. Submit your reference number and receipt in the portal.\n\n"
                    "Payment expires in {due_hours} hours."
                ).format(method=method.replace("_", " ").title()),
                "due_hours": 72,
            }
            return
        self._method = method
        self._config = MANUAL_METHODS[method]

    @property
    def name(self) -> str:
        return self._config["name"]

    @property
    def display_name(self) -> str:
        return self._config["display_name"]

    @property
    def state(self) -> ProviderState:
        """Manual providers are always available (no credentials needed)."""
        return ProviderState.CONFIGURED

    def supported_currencies(self) -> set[str]:
        return self._config["supported_currencies"]

    def supports_recurring(self) -> bool:
        return False

    def is_manual(self) -> bool:
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
        """
        Create a manual payment checkout.

        Returns checkout_url="" with instructions in metadata.
        """
        reference = _generate_manual_reference(
            prefix=self._method[:3].upper()
        )
        due_hours = self._config["due_hours"]
        amount_str = f"{amount:,.2f}"

        # Owner-configured instructions (from payment_method_configs) take
        # precedence over the built-in template. The checkout route passes the
        # config through metadata["owner_config"].
        owner_config = (metadata or {}).get("owner_config") or {}
        if owner_config.get("instructions"):
            instructions_text = self._build_owner_instructions(
                config=owner_config,
                reference=reference,
                amount_str=amount_str,
                currency=currency,
                due_hours=due_hours,
            )
        else:
            instructions_text = self._config["instructions_template"].format(
                reference=reference,
                amount=amount_str,
                currency=currency,
                due_hours=due_hours,
            )

        instructions = ManualPaymentInstructions(
            payment_method=self._method,
            payment_method_label=self._config["display_name"],
            instructions=instructions_text,
            reference=reference,
            amount_to_pay=f"{amount_str} {currency}",
            due_hours=due_hours,
        )

        logger.info(
            "Manual payment created: method=%s, reference=%s, amount=%s %s",
            self._method, reference, amount, currency,
        )

        return CheckoutSession(
            checkout_id=f"manual_{payment_id}",
            checkout_url="",  # No redirect for manual payments
            provider=self.name,
            payment_method=self._method,
            metadata={
                "manual_reference": reference,
                "manual_instructions": instructions.instructions,
                "manual_instructions_data": {
                    "payment_method": instructions.payment_method,
                    "payment_method_label": instructions.payment_method_label,
                    "reference": instructions.reference,
                    "amount_to_pay": instructions.amount_to_pay,
                    "due_hours": instructions.due_hours,
                },
                **(metadata or {}),
            },
        )

    def _build_owner_instructions(
        self,
        *,
        config: dict,
        reference: str,
        amount_str: str,
        currency: str,
        due_hours: int,
    ) -> str:
        """Build payment instructions from the Owner-configured method details."""
        lines: list[str] = []
        display_name = config.get("display_name") or self._config["display_name"]
        lines.append(f"To complete your payment via {display_name}:")

        beneficiary = config.get("beneficiary_name")
        rib = config.get("account_rib")
        phone = config.get("phone_number")
        branch = config.get("branch")

        if beneficiary:
            lines.append(f"Beneficiary: {beneficiary}")
        if rib:
            lines.append(f"Account RIB: {rib}")
        if phone:
            lines.append(f"Phone: {phone}")
        if branch:
            lines.append(f"Branch: {branch}")

        lines.append("")
        lines.append(f"Payment reference to provide: {reference}")
        lines.append(f"Exact amount to pay: {amount_str} {currency}")
        lines.append("")

        custom = (config.get("instructions") or "").strip()
        if custom:
            lines.append(custom)
        else:
            lines.append("Keep the receipt as proof of payment.")
            lines.append("Submit your reference number and receipt in the portal.")

        ref_instructions = (config.get("reference_instructions") or "").strip()
        if ref_instructions:
            lines.append("")
            lines.append(f"Reference instructions: {ref_instructions}")

        lines.append("")
        lines.append("Your payment will be verified within 24-48 hours after submission.")
        lines.append(f"Payment expires in {due_hours} hours.")
        return "\n".join(lines)

    async def confirm_payment(
        self,
        *,
        provider_payment_id: str,
    ) -> PaymentResult:
        """
        Manual payments cannot be confirmed via provider — they require
        admin/billing approval.
        """
        return PaymentResult(
            success=False,
            provider_payment_id=provider_payment_id,
            status="PENDING_VERIFICATION",
            payment_method=self._method,
            failure_reason="Manual payment requires admin approval",
        )

    def verify_webhook_signature(
        self,
        *,
        payload: bytes,
        signature: str,
    ) -> bool:
        """Manual payments have no webhooks."""
        return False

    async def parse_webhook_event(
        self,
        *,
        payload: bytes,
        headers: dict,
    ) -> Optional[WebhookEvent]:
        """Manual payments have no webhooks."""
        return None

    async def get_payment_status(
        self,
        *,
        provider_payment_id: str,
    ) -> PaymentResult:
        """Manual payment status can only be changed by admin/billing."""
        return PaymentResult(
            success=False,
            provider_payment_id=provider_payment_id,
            status="PENDING_VERIFICATION",
            payment_method=self._method,
        )

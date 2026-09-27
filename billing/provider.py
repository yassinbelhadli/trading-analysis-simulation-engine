"""
Abstract payment provider interface.

Every payment provider (Stripe, Binance Pay, Payzone, Cash Plus, etc.)
must implement this interface.  The rest of the system depends only on
this abstraction — never on concrete provider classes.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Provider capability / readiness states
# ---------------------------------------------------------------------------
class ProviderState(str, Enum):
    """Lifecycle state of a payment provider."""
    CONFIGURED = "CONFIGURED"          # Credentials present and valid
    NOT_CONFIGURED = "NOT_CONFIGURED"  # Credentials missing — cannot process
    UNAVAILABLE = "UNAVAILABLE"        # Provider explicitly unavailable (maintenance, region, etc.)
    ERROR = "ERROR"                    # Unexpected error during init / health check


# ---------------------------------------------------------------------------
# Data classes shared across all providers
# ---------------------------------------------------------------------------
@dataclass
class CheckoutSession:
    """Result of creating a checkout session with a provider."""
    checkout_id: str
    checkout_url: str
    provider: str
    payment_method: Optional[str] = None  # e.g. "binance_pay", "credit_card"
    metadata: dict = field(default_factory=dict)


@dataclass
class PaymentResult:
    """Result of confirming or querying a payment."""
    success: bool
    provider_payment_id: Optional[str] = None
    status: str = "unknown"  # maps to Payment.status
    payment_method: Optional[str] = None
    failure_reason: Optional[str] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class WebhookEvent:
    """Parsed webhook event from a provider."""
    event_id: str
    event_type: str  # checkout.session.completed, PAY_SUCCESS, etc.
    provider_payment_id: Optional[str] = None
    provider_checkout_id: Optional[str] = None
    status: str = "unknown"
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    payment_method: Optional[str] = None
    failure_reason: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Manual payment instructions (for providers that need customer action)
# ---------------------------------------------------------------------------
@dataclass
class ManualPaymentInstructions:
    """
    Instructions for a manual payment (Cash Plus, Chaabi Cash, Tashilat).

    The checkout flow uses these to show the customer what to do.
    """
    payment_method: str          # e.g. "cash_plus", "chaabi_cash", "tashilat"
    payment_method_label: str    # e.g. "Cash Plus", "Chaabi Cash"
    instructions: str            # Full text instructions for the customer
    reference: Optional[str] = None  # Reference number/token to present
    amount_to_pay: Optional[str] = None  # Formatted amount with currency
    due_hours: int = 72          # How long the customer has to pay
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Abstract provider interface
# ---------------------------------------------------------------------------
class PaymentProvider(abc.ABC):
    """
    Abstract base class for payment providers.

    Subclasses must implement every method.  The system never calls provider
    methods directly from routes — always through PaymentService which
    handles state transitions and idempotency.
    """

    # ------------------------------------------------------------------
    # Provider metadata
    # ------------------------------------------------------------------
    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Provider identifier (e.g. 'stripe', 'binance_pay')."""
        ...

    @property
    @abc.abstractmethod
    def display_name(self) -> str:
        """Human-readable name shown in UI (e.g. 'Stripe', 'Binance Pay')."""
        ...

    @property
    @abc.abstractmethod
    def state(self) -> ProviderState:
        """Current readiness state of the provider."""
        ...

    @property
    def is_configured(self) -> bool:
        """Whether the provider has valid credentials/configuration."""
        return self.state == ProviderState.CONFIGURED

    # ------------------------------------------------------------------
    # Capability flags
    # ------------------------------------------------------------------
    @abc.abstractmethod
    def supported_currencies(self) -> set[str]:
        """
        Return the set of ISO 4217 currency codes this provider supports
        for order creation.  Example: {"USD", "EUR", "MAD"}.
        """
        ...

    def supports_recurring(self) -> bool:
        """Whether this provider supports automatic recurring payments."""
        return False

    def is_manual(self) -> bool:
        """
        Whether this provider requires manual customer action
        (e.g. paying at a physical branch).
        """
        return False

    # ------------------------------------------------------------------
    # Checkout / payment lifecycle
    # ------------------------------------------------------------------
    @abc.abstractmethod
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
        Create a checkout session with the provider.

        For automatic providers: returns a checkout URL for redirect.
        For manual providers: returns checkout_url="" and manual instructions
        in metadata["manual_instructions"].

        Raises:
            PaymentProviderError: If the provider is unavailable or rejects the request.
        """
        ...

    @abc.abstractmethod
    async def confirm_payment(
        self,
        *,
        provider_payment_id: str,
    ) -> PaymentResult:
        """
        Confirm/query a payment by provider payment ID.

        Used to verify payment status after redirect or webhook delay.
        """
        ...

    @abc.abstractmethod
    def verify_webhook_signature(
        self,
        *,
        payload: bytes,
        signature: str,
    ) -> bool:
        """
        Verify that a webhook payload was signed by this provider.

        Returns True if valid, False otherwise.
        """
        ...

    @abc.abstractmethod
    async def parse_webhook_event(
        self,
        *,
        payload: bytes,
        headers: dict,
    ) -> Optional[WebhookEvent]:
        """
        Parse a raw webhook payload into a structured WebhookEvent.

        Returns None if the event is not relevant or not parseable.
        """
        ...

    @abc.abstractmethod
    async def get_payment_status(
        self,
        *,
        provider_payment_id: str,
    ) -> PaymentResult:
        """
        Query the current status of a payment from the provider.
        """
        ...

    # ------------------------------------------------------------------
    # Optional capabilities (override if supported)
    # ------------------------------------------------------------------
    async def refund_payment(
        self,
        *,
        provider_payment_id: str,
        amount: Optional[Decimal] = None,
        reason: Optional[str] = None,
    ) -> PaymentResult:
        """
        Refund a payment.  Override only if the provider supports refunds.

        Default raises PaymentProviderError.
        """
        raise PaymentProviderError(
            f"Refunds not supported by {self.name}",
            provider=self.name,
            code="NOT_SUPPORTED",
        )


class PaymentProviderError(Exception):
    """Raised when a payment provider operation fails."""
    def __init__(self, message: str, provider: str = "", code: str = ""):
        super().__init__(message)
        self.provider = provider
        self.code = code

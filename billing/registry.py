"""
Payment provider registry.

Central registry that manages all payment providers, handles routing
based on payment method + currency, and provides the correct provider
instance for each checkout.

13 independent payment methods organized into 4 categories:
  CARD / BANK:       ci_bank, cmi, payzone
  DIGITAL PAYMENTS:  binance_pay, apple_pay, google_pay
  LOCAL CASH:        cash_plus, wafa_cash
  CRYPTO:            btc, eth, sol, usdt

Usage:
    registry = PaymentProviderRegistry()
    provider = registry.get_provider("binance_pay")
    available = registry.get_available_methods("MAD")
"""
from __future__ import annotations

import logging
from typing import Optional

from billing.provider import PaymentProvider, ProviderState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Payment method catalog — every method is independent
# ---------------------------------------------------------------------------
PAYMENT_CATEGORIES = [
    {"key": "card_bank", "label": "Card / Bank"},
    {"key": "digital", "label": "Digital Payments"},
    {"key": "local_cash", "label": "Local Cash"},
    {"key": "crypto", "label": "Crypto"},
]

PAYMENT_METHODS = {
    # ------------------------------------------------------------------
    # CARD / BANK
    # ------------------------------------------------------------------
    "ci_bank": {
        "name": "ci_bank",
        "display_name": "CIH Bank / Card",
        "category": "card_bank",
        "type": "automatic",
        "description": "Pay with Visa / Mastercard via CIH Bank gateway",
        "subtitle": "Visa / Mastercard",
        "supported_currencies": {"MAD"},
        "icon": "credit_card",
        "availability": "available",  # available | payment_soon | coming_soon
    },
    "cmi": {
        "name": "cmi",
        "display_name": "CMI",
        "category": "card_bank",
        "type": "automatic",
        "description": "Card payment via CMI (Centrale Monétique Interbancaire)",
        "subtitle": "Card Payment",
        "supported_currencies": {"MAD"},
        "icon": "credit_card",
        "availability": "payment_soon",
    },
    "payzone": {
        "name": "payzone",
        "display_name": "Payzone",
        "category": "card_bank",
        "type": "automatic",
        "description": "Pay with credit/debit card via Payzone (Morocco)",
        "subtitle": "Card Payment",
        "supported_currencies": {"MAD", "USD", "EUR"},
        "icon": "credit_card",
        "availability": "payment_soon",
    },

    # ------------------------------------------------------------------
    # DIGITAL PAYMENTS
    # ------------------------------------------------------------------
    "binance_pay": {
        "name": "binance_pay",
        "display_name": "Binance Pay",
        "category": "digital",
        "type": "automatic",
        "description": "Pay with crypto (USDT, USDC, BTC, ETH, BNB) via Binance Pay",
        "subtitle": "Automatic",
        "supported_currencies": {"USD", "EUR", "MAD"},
        "icon": "currency",
        "availability": "available",
    },
    "apple_pay": {
        "name": "apple_pay",
        "display_name": "Apple Pay",
        "category": "digital",
        "type": "automatic",
        "description": "Pay via Apple Pay (requires gateway support)",
        "subtitle": "Automatic",
        "supported_currencies": {"USD", "EUR", "MAD"},
        "icon": "smartphone",
        "availability": "payment_soon",  # Only available if gateway supports it
    },
    "google_pay": {
        "name": "google_pay",
        "display_name": "Google Pay",
        "category": "digital",
        "type": "automatic",
        "description": "Pay via Google Pay (requires gateway support)",
        "subtitle": "Automatic",
        "supported_currencies": {"USD", "EUR", "MAD"},
        "icon": "smartphone",
        "availability": "payment_soon",  # Only available if gateway supports it
    },

    # ------------------------------------------------------------------
    # LOCAL CASH
    # ------------------------------------------------------------------
    "cash_plus": {
        "name": "cash_plus",
        "display_name": "Cash Plus",
        "category": "local_cash",
        "type": "manual",
        "description": "Pay in cash at any Cash Plus agency (5,300+ locations)",
        "subtitle": "Manual Verification",
        "supported_currencies": {"MAD"},
        "icon": "banknote",
        "availability": "available",
    },
    "wafa_cash": {
        "name": "wafa_cash",
        "display_name": "Wafa Cash",
        "category": "local_cash",
        "type": "manual",
        "description": "Pay in cash at any Wafa Cash point of sale",
        "subtitle": "Manual Verification",
        "supported_currencies": {"MAD"},
        "icon": "banknote",
        "availability": "available",
    },
    "cih_bank": {
        "name": "cih_bank",
        "display_name": "CIH Bank Transfer",
        "category": "local_cash",
        "type": "manual",
        "description": "Pay by bank transfer to the CIH account shown in the instructions",
        "subtitle": "Manual Verification",
        "supported_currencies": {"MAD"},
        "icon": "banknote",
        "availability": "available",
    },

    # ------------------------------------------------------------------
    # CRYPTO — manual on-chain payments with blockchain verification
    # ------------------------------------------------------------------
    "btc": {
        "name": "btc",
        "display_name": "Bitcoin",
        "category": "crypto",
        "type": "manual_crypto",
        "description": "Pay with BTC from any Bitcoin wallet",
        "subtitle": "Manual Verification",
        "supported_currencies": {"BTC"},
        "icon": "currency",
        "availability": "available",
        "networks": [
            {"id": "bitcoin", "label": "Bitcoin", "chain_id": "btc_mainnet"},
        ],
        "ticker": "BTC",
        "block_time_seconds": 600,
        "confirmations_required": 3,
    },
    "eth": {
        "name": "eth",
        "display_name": "Ethereum",
        "category": "crypto",
        "type": "manual_crypto",
        "description": "Pay with ETH from any Ethereum wallet",
        "subtitle": "Manual Verification",
        "supported_currencies": {"ETH"},
        "icon": "currency",
        "availability": "available",
        "networks": [
            {"id": "ethereum", "label": "Ethereum (ERC-20)", "chain_id": "eth_mainnet"},
        ],
        "ticker": "ETH",
        "block_time_seconds": 12,
        "confirmations_required": 12,
    },
    "sol": {
        "name": "sol",
        "display_name": "Solana",
        "category": "crypto",
        "type": "manual_crypto",
        "description": "Pay with SOL from any Solana wallet",
        "subtitle": "Manual Verification",
        "supported_currencies": {"SOL"},
        "icon": "currency",
        "availability": "available",
        "networks": [
            {"id": "solana", "label": "Solana", "chain_id": "sol_mainnet"},
        ],
        "ticker": "SOL",
        "block_time_seconds": 0.4,
        "confirmations_required": 32,
    },
    "usdt": {
        "name": "usdt",
        "display_name": "Tether",
        "category": "crypto",
        "type": "manual_crypto",
        "description": "Pay with USDT — select your network",
        "subtitle": "Manual Verification",
        "supported_currencies": {"USDT"},
        "icon": "currency",
        "availability": "available",
        "networks": [
            {"id": "trc20", "label": "TRC-20 (Tron)", "chain_id": "tron_mainnet"},
            {"id": "erc20", "label": "ERC-20 (Ethereum)", "chain_id": "eth_mainnet"},
            {"id": "bep20", "label": "BEP-20 (BNB Chain)", "chain_id": "bsc_mainnet"},
        ],
        "ticker": "USDT",
        "requires_network_selection": True,
        "block_time_seconds": 3,
        "confirmations_required": 20,
    },
}


# ---------------------------------------------------------------------------
# Provider availability overrides (runtime, from env / feature flags)
# ---------------------------------------------------------------------------
# Apple Pay and Google Pay are only AVAILABLE if the active payment gateway
# actually supports them.  This map is the single source of truth.
# When False, the method shows "Payment Soon" instead of "Available".
_DIGITAL_WALLET_OVERRIDES: dict[str, bool] = {
    "apple_pay": False,   # flip to True once gateway confirms support
    "google_pay": False,  # flip to True once gateway confirms support
}


class PaymentProviderRegistry:
    """
    Central registry for all payment providers.

    Lazily instantiates providers on first access.
    Provides methods to:
    - Get a provider by name
    - List available methods for a currency
    - Check provider health/status
    """

    def __init__(self):
        self._providers: dict[str, PaymentProvider] = {}
        self._initialized = False

    def _ensure_providers(self) -> None:
        """Lazy-initialize all provider instances."""
        if self._initialized:
            return

        # --- CARD / BANK ---
        try:
            from billing.ci_bank_provider import CIBankProvider
            self._providers["ci_bank"] = CIBankProvider()
        except Exception as e:
            logger.warning("Failed to initialize CIH Bank provider: %s", e)

        # CMI — no implementation yet, placeholder only
        # self._providers["cmi"] is intentionally absent

        # Payzone
        try:
            from billing.payzone_provider import PayzoneProvider
            self._providers["payzone"] = PayzoneProvider()
        except Exception as e:
            logger.warning("Failed to initialize Payzone provider: %s", e)

        # --- DIGITAL PAYMENTS ---
        # Binance Pay
        try:
            from billing.binance_pay_provider import BinancePayProvider
            self._providers["binance_pay"] = BinancePayProvider()
        except Exception as e:
            logger.warning("Failed to initialize Binance Pay provider: %s", e)

        # Apple Pay / Google Pay — delegated to the active card gateway
        # (only functional when the gateway explicitly supports them)

        # --- LOCAL CASH ---
        try:
            from billing.manual_provider import ManualPaymentProvider
            self._providers["cash_plus"] = ManualPaymentProvider(method="cash_plus")
            self._providers["wafa_cash"] = ManualPaymentProvider(method="wafa_cash")
            self._providers["cih_bank"] = ManualPaymentProvider(method="cih_bank")
        except Exception as e:
            logger.warning("Failed to initialize manual cash providers: %s", e)

        # --- CRYPTO ---
        try:
            from billing.crypto_provider import CryptoPaymentProvider
            for coin in ("btc", "eth", "sol", "usdt"):
                self._providers[coin] = CryptoPaymentProvider(coin=coin)
        except Exception as e:
            logger.warning("Failed to initialize crypto providers: %s", e)

        self._initialized = True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_provider(self, name: str) -> Optional[PaymentProvider]:
        """Get a provider by name. Returns None if not found."""
        self._ensure_providers()
        return self._providers.get(name)

    def get_all_providers(self) -> dict[str, PaymentProvider]:
        """Get all registered providers."""
        self._ensure_providers()
        return dict(self._providers)

    def get_available_methods(self, currency: str) -> list[dict]:
        """
        Get available payment methods for a given currency.

        Returns a list of method info dicts grouped by category,
        sorted within each group: configured automatic first, then manual.
        """
        self._ensure_providers()
        currency_upper = currency.upper()
        result: list[dict] = []

        for method_name, method_info in PAYMENT_METHODS.items():
            # Crypto methods are always available regardless of currency filter
            if method_info.get("category") != "crypto":
                if currency_upper not in method_info.get("supported_currencies", set()):
                    continue

            provider = self._providers.get(method_name)

            # Determine effective availability
            availability = method_info.get("availability", "available")
            if method_name in _DIGITAL_WALLET_OVERRIDES:
                availability = "available" if _DIGITAL_WALLET_OVERRIDES[method_name] else "payment_soon"

            # If provider exists, use its state
            is_configured = False
            provider_state = ProviderState.NOT_CONFIGURED.value
            if provider:
                is_configured = provider.is_configured
                provider_state = provider.state.value

            result.append({
                "name": method_name,
                "display_name": method_info.get("display_name", method_name),
                "category": method_info.get("category", "other"),
                "type": method_info.get("type", "automatic"),
                "description": method_info.get("description", ""),
                "subtitle": method_info.get("subtitle", ""),
                "icon": method_info.get("icon", "credit_card"),
                "state": provider_state,
                "is_configured": is_configured,
                "is_manual": method_info.get("type", "automatic") in ("manual", "manual_crypto"),
                "availability": availability,
                # Crypto-specific fields
                "networks": method_info.get("networks", []),
                "ticker": method_info.get("ticker"),
                "requires_network_selection": method_info.get("requires_network_selection", False),
                "confirmations_required": method_info.get("confirmations_required"),
            })

        return result

    def get_methods_grouped(self, currency: str) -> dict[str, list[dict]]:
        """
        Get available payment methods grouped by category.

        Returns: { "card_bank": [...], "digital": [...], "local_cash": [...], "crypto": [...] }
        """
        methods = self.get_available_methods(currency)
        grouped: dict[str, list[dict]] = {cat["key"]: [] for cat in PAYMENT_CATEGORIES}
        grouped["other"] = []
        for m in methods:
            cat = m.get("category", "other")
            if cat in grouped:
                grouped[cat].append(m)
        return grouped

    def get_provider_status_all(self) -> list[dict]:
        """Get status of all providers for admin/owner view."""
        self._ensure_providers()
        result = []

        for method_name, method_info in PAYMENT_METHODS.items():
            provider = self._providers.get(method_name)

            availability = method_info.get("availability", "available")
            if method_name in _DIGITAL_WALLET_OVERRIDES:
                availability = "available" if _DIGITAL_WALLET_OVERRIDES[method_name] else "payment_soon"

            if provider is None:
                result.append({
                    "name": method_name,
                    "display_name": method_info.get("display_name", method_name),
                    "category": method_info.get("category", "other"),
                    "type": method_info.get("type", "automatic"),
                    "state": ProviderState.UNAVAILABLE.value,
                    "is_configured": False,
                    "is_manual": method_info.get("type", "automatic") in ("manual", "manual_crypto"),
                    "availability": availability,
                    "supported_currencies": sorted(method_info.get("supported_currencies", set())),
                })
                continue

            result.append({
                "name": method_name,
                "display_name": method_info.get("display_name", method_name),
                "category": method_info.get("category", "other"),
                "type": method_info.get("type", "automatic"),
                "state": provider.state.value,
                "is_configured": provider.is_configured,
                "is_manual": provider.is_manual(),
                "availability": availability,
                "supported_currencies": sorted(provider.supported_currencies()),
            })

        return result


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_registry: Optional[PaymentProviderRegistry] = None


def get_registry() -> PaymentProviderRegistry:
    """Get or create the global payment provider registry."""
    global _registry
    if _registry is None:
        _registry = PaymentProviderRegistry()
    return _registry

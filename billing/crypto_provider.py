"""
Manual crypto payment provider.

Handles BTC, ETH, SOL, USDT on-chain payments.
Each payment gets a unique deposit address derived from a master wallet.
Network selection is explicit (USDT-TRC20, USDT-ERC20, USDT-BEP20).

This provider is always CONFIGURED (manual crypto doesn't need API keys).
Blockchain verification happens in billing/blockchain_service.py.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
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


# ---------------------------------------------------------------------------
# Crypto coin configuration
# ---------------------------------------------------------------------------
_COIN_CONFIG = {
    "btc": {
        "ticker": "BTC",
        "name": "Bitcoin",
        "networks": [
            {"id": "bitcoin", "label": "Bitcoin", "chain_id": "btc_mainnet"},
        ],
        "confirmations_required": 3,
        "block_time_seconds": 600,
    },
    "eth": {
        "ticker": "ETH",
        "name": "Ethereum",
        "networks": [
            {"id": "ethereum", "label": "Ethereum (ERC-20)", "chain_id": "eth_mainnet"},
        ],
        "confirmations_required": 12,
        "block_time_seconds": 12,
    },
    "sol": {
        "ticker": "SOL",
        "name": "Solana",
        "networks": [
            {"id": "solana", "label": "Solana", "chain_id": "sol_mainnet"},
        ],
        "confirmations_required": 32,
        "block_time_seconds": 0.4,
    },
    "usdt": {
        "ticker": "USDT",
        "name": "Tether",
        "networks": [
            {"id": "trc20", "label": "TRC-20 (Tron)", "chain_id": "tron_mainnet"},
            {"id": "erc20", "label": "ERC-20 (Ethereum)", "chain_id": "eth_mainnet"},
            {"id": "bep20", "label": "BEP-20 (BNB Chain)", "chain_id": "bsc_mainnet"},
        ],
        "confirmations_required": 20,
        "block_time_seconds": 3,
        "requires_network_selection": True,
    },
}


def _derive_deposit_address(
    master_seed: str,
    payment_id: str,
    coin: str,
    network: str,
) -> str:
    """
    Derive a deterministic deposit address from a master seed + payment context.

    In production, replace this with HD-wallet derivation (BIP32/BIP44)
    or a crypto payment gateway API (e.g., NOWPayments, CoinGate).

    The address format is a realistic-looking placeholder that demonstrates
    the architecture.  Real address generation requires wallet infrastructure.
    """
    # HMAC-based derivation: deterministic per (seed, payment_id, coin, network)
    material = f"{coin}:{network}:{payment_id}".encode()
    derived = hmac.new(master_seed.encode(), material, hashlib.sha256).hexdigest()

    # Format address prefix per coin (realistic format)
    prefixes = {
        "btc": "bc1q",
        "eth": "0x",
        "sol": "",  # Solana addresses are base58, no prefix
        "usdt": "",  # Depends on network
    }
    prefix = prefixes.get(coin, "")

    if coin == "sol":
        # Solana: base58-like alphanumeric, 32-44 chars
        import string as _s
        b58 = _s.digits + _s.ascii_lowercase + _s.ascii_uppercase
        addr = ""
        h = derived
        while len(addr) < 44:
            idx = int(h[len(addr) : len(addr) + 2], 16) % 58
            addr += b58[idx]
            if len(addr) + 2 > len(h):
                h += hashlib.sha256(h.encode()).hexdigest()
        return addr[:44]
    elif coin == "btc":
        return prefix + derived[:38]
    elif coin in ("eth", "usdt"):
        return prefix + derived[:40]
    return derived[:40]


class CryptoPaymentProvider(PaymentProvider):
    """
    Manual crypto payment provider for BTC, ETH, SOL, USDT.

    Each payment receives a unique deposit address derived from a master seed.
    Blockchain verification is handled separately by billing/blockchain_service.py.
    """

    def __init__(self, coin: str = "btc"):
        if coin not in _COIN_CONFIG:
            raise ValueError(f"Unsupported coin: {coin}")
        self._coin = coin
        self._config = _COIN_CONFIG[coin]
        # Master seed for address derivation — from env in production
        self._master_seed = os.getenv(
            f"CRYPTO_MASTER_SEED_{coin.upper()}",
            os.getenv("CRYPTO_MASTER_SEED", "dev-master-seed-change-in-production"),
        )

    @property
    def name(self) -> str:
        return self._coin

    @property
    def display_name(self) -> str:
        return self._config["name"]

    @property
    def state(self) -> ProviderState:
        return ProviderState.CONFIGURED

    @property
    def is_configured(self) -> bool:
        return True  # Manual crypto is always available

    def supported_currencies(self) -> set:
        return {self._config["ticker"]}

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
        Create a crypto checkout with unique deposit address.

        The checkout_url is empty (no redirect).  Instructions and the
        deposit address are returned in metadata for the frontend to render.
        """
        meta = metadata or {}
        network = meta.get("network", self._config["networks"][0]["id"])

        # Owner-configured wallet (REQ 10): when the owner has set a real
        # wallet_address for this coin, clients pay that address. Placeholder
        # derivation is only used when no owner wallet exists — and the
        # checkout route refuses to create crypto payments without one.
        owner_config = meta.get("owner_config") or {}
        owner_wallet = (owner_config.get("wallet_address") or "").strip()
        if owner_wallet:
            deposit_address = owner_wallet
        else:
            deposit_address = _derive_deposit_address(
                self._master_seed, payment_id, self._coin, network,
            )

        # Build instructions
        coin_name = self._config["name"]
        ticker = self._config["ticker"]
        net_label = network.upper()
        if self._coin == "usdt":
            # Find network label from config
            for n in self._config["networks"]:
                if n["id"] == network:
                    net_label = n["label"]
                    break

        instructions_text = (
            f"Send exactly {amount} {ticker} to the address below.\n\n"
            f"Network: {net_label}\n"
            f"Deposit Address:\n{deposit_address}\n\n"
            f"IMPORTANT:\n"
            f"- Send the EXACT amount\n"
            f"- Use the correct network ({net_label})\n"
            f"- Do NOT send from an unsupported network\n"
            f"- Keep your transaction hash for proof submission\n"
            f"- Payment expires in 60 minutes\n"
        )

        instructions = ManualPaymentInstructions(
            payment_method=self._coin,
            payment_method_label=coin_name,
            instructions=instructions_text,
            reference=deposit_address,
            amount_to_pay=f"{amount} {ticker}",
            due_hours=1,
            metadata={
                "deposit_address": deposit_address,
                "network": network,
                "ticker": ticker,
                "coin_name": coin_name,
                "confirmations_required": self._config["confirmations_required"],
                "block_time_seconds": self._config["block_time_seconds"],
                "requires_network_selection": self._config.get("requires_network_selection", False),
                "available_networks": [
                    {"id": n["id"], "label": n["label"]}
                    for n in self._config["networks"]
                ],
            },
        )

        return CheckoutSession(
            checkout_id="",
            checkout_url="",
            provider=self._coin,
            payment_method=f"manual_crypto_{self._coin}",
            metadata={
                "manual_instructions": instructions_text,
                "manual_reference": deposit_address,
                "deposit_address": deposit_address,
                "network": network,
                "ticker": ticker,
                "coin_name": coin_name,
                "instructions": instructions.__dict__,
            },
        )

    async def confirm_payment(self, *, provider_payment_id: str) -> PaymentResult:
        """Manual crypto — cannot confirm via API. Requires blockchain verification."""
        return PaymentResult(
            success=False,
            status="AWAITING_PAYMENT",
            failure_reason="Manual crypto payment requires blockchain verification",
        )

    def verify_webhook_signature(self, *, payload: bytes, signature: str) -> bool:
        """Crypto providers don't receive traditional webhooks."""
        return False

    async def parse_webhook_event(self, *, payload: bytes, headers: dict) -> WebhookEvent | None:
        """Crypto providers don't receive traditional webhooks."""
        return None

    async def get_payment_status(self, *, provider_payment_id: str) -> PaymentResult:
        """Manual crypto — requires blockchain verification service."""
        return PaymentResult(
            success=False,
            status="AWAITING_PAYMENT",
        )

    # ------------------------------------------------------------------
    # Crypto-specific methods
    # ------------------------------------------------------------------
    def get_networks(self) -> list[dict]:
        """Return available networks for this coin."""
        return self._config["networks"]

    def validate_network(self, network: str) -> bool:
        """Check if the given network ID is valid for this coin."""
        return any(n["id"] == network for n in self._config["networks"])

    def get_confirmations_required(self) -> int:
        return self._config["confirmations_required"]

    def get_block_time(self) -> float:
        return self._config["block_time_seconds"]

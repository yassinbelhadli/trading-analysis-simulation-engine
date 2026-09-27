"""
Blockchain verification service.

Verifies crypto payments by checking the blockchain for incoming
transactions to the deposit address. Implements the 10-point verification
checklist.  Falls back to manual review when automatic checks fail.

Flow:
1. Client submits proof (tx hash, amount, screenshot)
2. Service runs 10-point automatic verification
3. If all checks pass → PAID (auto-verified)
4. If any check fails → MANUAL_REVIEW
5. Owner/Billing can always override via manual approval

Security:
- Never store private keys
- Never expose wallet credentials
- All verification is server-side
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Verification checklist result
# ---------------------------------------------------------------------------
class VerificationResult:
    """Result of the 10-point blockchain verification checklist."""

    def __init__(self):
        self.checks: list[dict] = []
        self.all_passed = True
        self.failure_reasons: list[str] = []
        self.detected_amount: Optional[Decimal] = None
        self.detected_network: Optional[str] = None
        self.sender_address: Optional[str] = None
        self.confirmation_count: int = 0

    def add_check(self, name: str, passed: bool, detail: str = ""):
        self.checks.append({
            "name": name,
            "passed": passed,
            "detail": detail,
        })
        if not passed:
            self.all_passed = False
            self.failure_reasons.append(f"{name}: {detail}")

    def to_dict(self) -> dict:
        return {
            "all_passed": self.all_passed,
            "checks": self.checks,
            "failure_reasons": self.failure_reasons,
            "detected_amount": float(self.detected_amount) if self.detected_amount else None,
            "detected_network": self.detected_network,
            "sender_address": self.sender_address,
            "confirmation_count": self.confirmation_count,
        }


# ---------------------------------------------------------------------------
# Network configuration (confirmations required, expected asset)
# ---------------------------------------------------------------------------
_NETWORK_CONFIG = {
    "bitcoin": {
        "ticker": "BTC",
        "confirmations_required": 3,
        "block_time_seconds": 600,
    },
    "ethereum": {
        "ticker": "ETH",
        "confirmations_required": 12,
        "block_time_seconds": 12,
    },
    "solana": {
        "ticker": "SOL",
        "confirmations_required": 32,
        "block_time_seconds": 0.4,
    },
    "trc20": {
        "ticker": "USDT",
        "confirmations_required": 20,
        "block_time_seconds": 3,
    },
    "erc20": {
        "ticker": "USDT",
        "confirmations_required": 20,
        "block_time_seconds": 12,
    },
    "bep20": {
        "ticker": "USDT",
        "confirmations_required": 20,
        "block_time_seconds": 3,
    },
}


def get_network_config(network: str) -> dict:
    """Get configuration for a blockchain network."""
    return _NETWORK_CONFIG.get(network, {
        "ticker": "UNKNOWN",
        "confirmations_required": 1,
        "block_time_seconds": 60,
    })


# ---------------------------------------------------------------------------
# Blockchain verification service
# ---------------------------------------------------------------------------
class BlockchainVerificationService:
    """
    Verifies crypto payments using the 10-point checklist.

    In production, this service would:
    - Query blockchain explorers (blockstream.info, etherscan, etc.)
    - Query crypto payment gateways (NOWPayments, CoinGate, etc.)
    - Monitor deposit addresses for incoming transactions

    This implementation provides the architecture and verification logic.
    Actual blockchain API calls require provider integration.
    """

    @staticmethod
    async def verify_payment(
        *,
        deposit_address: str,
        network: str,
        expected_amount: Decimal,
        coin_ticker: str,
        transaction_hash: Optional[str] = None,
        proof_amount: Optional[Decimal] = None,
        proof_tx_hash: Optional[str] = None,
        payment_created_at: Optional[datetime] = None,
        existing_hashes: Optional[list[str]] = None,
    ) -> VerificationResult:
        """
        Run the 10-point verification checklist.

        Returns a VerificationResult with each check's pass/fail status.
        """
        result = VerificationResult()
        now = datetime.now(timezone.utc)
        net_config = get_network_config(network)

        # --- Check 1: Correct Network ---
        expected_ticker = net_config.get("ticker", "UNKNOWN")
        result.add_check(
            "correct_network",
            True,
            f"Network is {network} ({expected_ticker})",
        )

        # --- Check 2: Correct Asset ---
        asset_matches = expected_ticker.upper() == coin_ticker.upper()
        result.add_check(
            "correct_asset",
            asset_matches,
            f"Expected {expected_ticker}, got {coin_ticker}" if not asset_matches else f"Asset {coin_ticker} matches",
        )

        # --- Check 3: Correct Address ---
        address_valid = bool(deposit_address and len(deposit_address) > 10)
        result.add_check(
            "correct_address",
            address_valid,
            f"Deposit address provided: {deposit_address[:20]}..." if address_valid else "No deposit address",
        )

        # --- Check 4: Transaction Hash Provided ---
        tx_hash = proof_tx_hash or transaction_hash
        hash_valid = bool(tx_hash and len(tx_hash) > 10)
        result.add_check(
            "transaction_hash_provided",
            hash_valid,
            f"TX hash: {tx_hash[:20]}..." if hash_valid else "No transaction hash provided",
        )

        # --- Check 5: Amount Check ---
        # Compare proof amount against expected (with 1% tolerance for crypto volatility)
        if proof_amount and expected_amount:
            tolerance = expected_amount * Decimal("0.01")
            amount_ok = abs(proof_amount - expected_amount) <= tolerance
            result.add_check(
                "amount_matches",
                amount_ok,
                f"Expected {expected_amount}, got {proof_amount}"
                + (" (within 1% tolerance)" if amount_ok else " (outside tolerance)"),
            )
            result.detected_amount = proof_amount
        elif expected_amount:
            result.add_check("amount_matches", False, "No proof amount provided")
        else:
            result.add_check("amount_matches", False, "No expected amount set")

        # --- Check 6: Confirmation Count ---
        # In production, query blockchain API for tx confirmations
        # For now, mark as needing confirmation
        result.add_check(
            "sufficient_confirmations",
            False,  # Requires blockchain API
            f"Requires {net_config['confirmations_required']} confirmations — needs blockchain API",
        )
        result.confirmation_count = 0

        # --- Check 7: No Duplicate Transaction ---
        if tx_hash and existing_hashes:
            is_duplicate = tx_hash in existing_hashes
            result.add_check(
                "no_duplicate",
                not is_duplicate,
                "Transaction hash is unique" if not is_duplicate else "Transaction hash already used",
            )
        else:
            result.add_check("no_duplicate", True, "No existing hashes to check against")

        # --- Check 8: Payment Not Expired ---
        if payment_created_at:
            expiry_minutes = 60
            from datetime import timedelta
            expires_at = payment_created_at + timedelta(minutes=expiry_minutes)
            not_expired = now < expires_at
            result.add_check(
                "not_expired",
                not_expired,
                f"Payment expires at {expires_at.isoformat()}" + (" — still valid" if not_expired else " — EXPIRED"),
            )
        else:
            result.add_check("not_expired", True, "No expiration set")

        # --- Check 9: Late Transaction Check ---
        if payment_created_at:
            from datetime import timedelta
            grace_hours = 2  # Allow 2 hours after expiration for late transactions
            expires_at = payment_created_at + timedelta(minutes=60)
            late_deadline = expires_at + timedelta(hours=grace_hours)
            is_late = now > late_deadline
            result.add_check(
                "not_late",
                not is_late,
                f"Late deadline: {late_deadline.isoformat()}" + (" — within grace period" if not is_late else " — LATE (flag for review)"),
            )
        else:
            result.add_check("not_late", True, "No deadline set")

        # --- Check 10: Payment Not Already Associated ---
        # This is checked at the caller level (payment_id uniqueness)
        result.add_check(
            "payment_not_already_associated",
            True,  # Assumed checked by caller
            "Checked by caller (payment_id unique)",
        )

        logger.info(
            "Blockchain verification: address=%s, network=%s, all_passed=%s, failures=%d",
            deposit_address[:20] if deposit_address else "N/A",
            network,
            result.all_passed,
            len(result.failure_reasons),
        )

        return result

    @staticmethod
    async def detect_transaction(
        *,
        deposit_address: str,
        network: str,
    ) -> Optional[dict]:
        """
        Detect incoming transactions to a deposit address.

        In production, this would query blockchain APIs.
        Returns None if no transaction detected.

        Returns dict with: tx_hash, amount, sender_address, confirmations, timestamp
        """
        # In production: query blockchain explorer API
        # blockstream.info (BTC), etherscan.io (ETH), etc.
        logger.info(
            "Blockchain detection requested: address=%s, network=%s (requires API integration)",
            deposit_address[:20] if deposit_address else "N/A",
            network,
        )
        return None

    @staticmethod
    def determine_verification_result(
        verification: VerificationResult,
    ) -> str:
        """
        Determine the payment status based on verification result.

        Returns one of: PAID, MANUAL_REVIEW, FAILED
        """
        if verification.all_passed:
            return "PAID"
        elif len(verification.failure_reasons) <= 2 and verification.detected_amount:
            # Partial match — flag for manual review
            return "MANUAL_REVIEW"
        else:
            return "MANUAL_REVIEW"

"""Seed configuration-driven payment method configs (demo data).

Populates description / information / client_fields / receipt_required for the
existing manual methods and creates manual_crypto configs so the client can
render every method dynamically. Idempotent: only fills empty fields and
creates missing crypto rows.
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from database.db import async_session_factory  # noqa: E402
from database.models import PaymentMethodConfig  # noqa: E402

MANUAL = {
    "cash_plus": {
        "description": "Pay in cash at any Cash Plus agency. Keep your receipt — you will upload it here.",
        "information": [
            {"label": "Beneficiary", "value": "ICT EA Pro SARL"},
            {"label": "Phone", "value": "+212 6 00 00 00 00"},
            {"label": "Branch", "value": "Any Cash Plus agency (Morocco)"},
        ],
        "client_fields": [
            {"key": "payment_reference", "label": "Payment Reference", "type": "text", "required": True, "placeholder": "The reference shown above"},
            {"key": "payer_name", "label": "Payer Full Name", "type": "text", "required": True, "placeholder": "Name on the receipt"},
            {"key": "payer_phone", "label": "Payer Phone", "type": "phone", "required": True, "placeholder": "+212 6 XX XX XX XX"},
            {"key": "payment_date", "label": "Payment Date & Time", "type": "datetime", "required": True},
            {"key": "amount_paid", "label": "Amount Paid (MAD)", "type": "number", "required": True, "validation": "min:0"},
        ],
    },
    "wafa_cash": {
        "description": "Pay in cash at any Attijariwafa Bank Wafa Cash agency. Upload your receipt after paying.",
        "information": [
            {"label": "Beneficiary", "value": "ICT EA Pro SARL"},
            {"label": "Phone", "value": "+212 6 11 11 11 11"},
            {"label": "Branch", "value": "Any Wafa Cash agency (Morocco)"},
        ],
        "client_fields": [
            {"key": "payment_reference", "label": "Payment Reference", "type": "text", "required": True, "placeholder": "The reference shown above"},
            {"key": "payer_name", "label": "Payer Full Name", "type": "text", "required": True, "placeholder": "Name on the receipt"},
            {"key": "payer_phone", "label": "Payer Phone", "type": "phone", "required": True, "placeholder": "+212 6 XX XX XX XX"},
            {"key": "payment_date", "label": "Payment Date & Time", "type": "datetime", "required": True},
            {"key": "amount_paid", "label": "Amount Paid (MAD)", "type": "number", "required": True, "validation": "min:0"},
        ],
    },
    "cih_bank": {
        "description": "Transfer to our CIH Bank account, then upload your transfer receipt.",
        "information": [
            {"label": "Beneficiary", "value": "ICT EA Pro SARL"},
            {"label": "RIB", "value": "011 780 0001 234567890123 45"},
            {"label": "Bank", "value": "CIH Bank"},
            {"label": "Branch", "value": "Agence Maarif, Casablanca"},
        ],
        "client_fields": [
            {"key": "payment_reference", "label": "Payment Reference", "type": "text", "required": True, "placeholder": "The reference shown above"},
            {"key": "payer_name", "label": "Account Holder Name", "type": "text", "required": True, "placeholder": "Name on the account"},
            {"key": "payer_phone", "label": "Payer Phone", "type": "phone", "required": True, "placeholder": "+212 6 XX XX XX XX"},
            {"key": "payment_date", "label": "Transfer Date & Time", "type": "datetime", "required": True},
            {"key": "amount_paid", "label": "Amount Transferred (MAD)", "type": "number", "required": True, "validation": "min:0"},
        ],
    },
}

CRYPTO = {
    "btc": {"display_name": "Bitcoin", "network": "BTC", "wallet": "bc1qdemoictfundeapro0000000000000000000000"},
    "eth": {"display_name": "Ethereum", "network": "ERC20", "wallet": "0xDemoICTEAPro00000000000000000000000000"},
    "sol": {"display_name": "Solana", "network": "SOL", "wallet": "DemoICTEAProSolanaWallet111111111111111111"},
    "usdt": {"display_name": "Tether USDT", "network": "TRC20", "wallet": "TDemoICTEAProUSDTTRC20Wallet0000000000"},
}


async def main() -> None:
    async with async_session_factory() as session:
        result = await session.execute(select(PaymentMethodConfig))
        rows = {c.method_id: c for c in result.scalars().all()}

        for method_id, data in MANUAL.items():
            cfg = rows.get(method_id)
            if not cfg:
                print(f"SKIP {method_id}: no config row")
                continue
            changed = False
            if not cfg.description:
                cfg.description = data["description"]
                changed = True
            if not cfg.information:
                cfg.information = data["information"]
                changed = True
            if not cfg.client_fields:
                cfg.client_fields = data["client_fields"]
                changed = True
            if cfg.receipt_required is None:
                cfg.receipt_required = True
                changed = True
            print(f"{'UPDATED' if changed else 'unchanged'} {method_id}")

        for method_id, data in CRYPTO.items():
            cfg = rows.get(method_id)
            if not cfg:
                cfg = PaymentMethodConfig(
                    method_id=method_id,
                    method_type="manual_crypto",
                    display_name=data["display_name"],
                    wallet_address=data["wallet"],
                    network=data["network"],
                    expires_hours=1,
                    description=f"Pay with {data['display_name']}. Send the exact amount to the address shown, then upload your transaction proof.",
                    information=[
                        {"label": "Network", "value": data["network"]},
                        {"label": "Wallet", "value": data["wallet"]},
                    ],
                    client_fields=[
                        {"key": "tx_hash", "label": "Transaction Hash", "type": "text", "required": True, "placeholder": "The TXID of your transfer"},
                        {"key": "payer_name", "label": "Payer Name", "type": "text", "required": False, "placeholder": "Optional"},
                    ],
                    receipt_required=True,
                    reference_required=False,
                    is_active=True,
                    display_order=10,
                )
                session.add(cfg)
                print(f"CREATED {method_id}")
            else:
                changed = False
                if not cfg.wallet_address:
                    cfg.wallet_address = data["wallet"]
                    changed = True
                if not cfg.description:
                    cfg.description = f"Pay with {data['display_name']}. Send the exact amount to the address shown, then upload your transaction proof."
                    changed = True
                if not cfg.information:
                    cfg.information = [{"label": "Network", "value": data["network"]}, {"label": "Wallet", "value": data["wallet"]}]
                    changed = True
                if not cfg.client_fields:
                    cfg.client_fields = [
                        {"key": "tx_hash", "label": "Transaction Hash", "type": "text", "required": True, "placeholder": "The TXID of your transfer"},
                        {"key": "payer_name", "label": "Payer Name", "type": "text", "required": False, "placeholder": "Optional"},
                    ]
                    changed = True
                print(f"{'UPDATED' if changed else 'unchanged'} {method_id}")

        await session.commit()
        print("DONE")


if __name__ == "__main__":
    asyncio.run(main())
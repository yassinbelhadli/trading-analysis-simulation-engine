"""
Client payment routes — checkout, payment history, receipt download.

All routes require authentication (get_current_user).
All price calculations are server-side (never trust frontend values).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from billing.payment_service import PaymentService, PaymentServiceError
from billing.provider import PaymentProviderError, WebhookEvent
from billing.receipt_service import ReceiptService
from database.db import get_session
from database.models import (
    Coupon,
    Payment,
    PlanDefinition,
    Receipt,
    Subscription,
    User,
)
from security.auth import get_current_user
from api.services.coupon_service import (
    VALID_CURRENCIES,
    CouponValidationError,
    get_plan_price,
    validate_coupon_for_purchase,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/client", tags=["client", "payments"])

# ---------------------------------------------------------------------------
# Proof-of-payment file storage
# ---------------------------------------------------------------------------
from pathlib import Path

PROOF_STORAGE_DIR = Path(__file__).resolve().parents[3] / "storage" / "uploads" / "proofs"
ALLOWED_PROOF_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}
ALLOWED_PROOF_MEDIA = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "application/pdf": ".pdf",
}
MAX_PROOF_BYTES = 10 * 1024 * 1024  # 10 MB


def _safe_proof_filename(filename: str) -> str:
    """Sanitize an uploaded filename to a safe basename."""
    name = Path(filename or "proof").name
    name = "".join(ch for ch in name if ch.isalnum() or ch in "._-")
    return name or "proof"

# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class CheckoutRequest(BaseModel):
    plan_id: str
    currency: str = "USD"
    coupon_code: Optional[str] = None
    payment_method: str = "stripe"  # All 13 methods supported
    network: Optional[str] = None  # Required for crypto (usdt): trc20/erc20/bep20
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


class ManualPaymentSubmitRequest(BaseModel):
    manual_reference: Optional[str] = None
    manual_proof_url: Optional[str] = None
    payer_name: Optional[str] = None
    payer_phone: Optional[str] = None
    payment_date: Optional[str] = None  # ISO datetime when the payer actually paid
    amount_paid: Optional[float] = None  # amount the payer actually transferred
    # Configuration-driven: values for the owner-defined client fields.
    # Keys match the field "key" in the method's client_fields configuration.
    client_fields_data: Optional[dict] = None


class CryptoProofSubmitRequest(BaseModel):
    tx_hash: str
    amount_sent: float
    network: str
    screenshot_url: Optional[str] = None
    note: Optional[str] = None


class PaymentHistoryResponse(BaseModel):
    payments: list[dict]
    total: int


class ReceiptResponse(BaseModel):
    receipt: dict


# ---------------------------------------------------------------------------
# Helper: get payment service with provider from registry
# ---------------------------------------------------------------------------

def _get_payment_service_for_method(method_name: str = "stripe") -> PaymentService:
    """Create a PaymentService with the correct provider from the registry.

    Owner-created configuration-driven methods (not in the registry) are
    served by the generic ManualPaymentProvider, which accepts any method
    name and renders the owner's own instructions from owner_config.
    """
    from billing.registry import get_registry
    registry = get_registry()
    provider = registry.get_provider(method_name)
    if provider is None:
        from billing.manual_provider import ManualPaymentProvider
        provider = ManualPaymentProvider(method_name)
    return PaymentService(provider)


# ---------------------------------------------------------------------------
# GET /client/payment-methods — list available payment methods for currency
# ---------------------------------------------------------------------------

@router.get("/payment-methods")
async def list_payment_methods(
    currency: str = "USD",
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """List available payment methods for a given currency, grouped by category.

    Owner-config gating (REQ 4/10): manual methods are only offered when the
    owner has an active, non-archived config; manual_crypto additionally
    requires a real wallet address — placeholder addresses are never shown.
    """
    from billing.registry import get_registry
    registry = get_registry()
    currency_upper = currency.upper()
    ALL_VALID = VALID_CURRENCIES | {"BTC", "ETH", "SOL", "USDT"}
    if currency_upper not in ALL_VALID:
        raise HTTPException(400, f"Invalid currency: {currency_upper}")

    methods = registry.get_available_methods(currency_upper)

    # Load owner configs once and gate manual/manual_crypto methods on them
    from database.models import PaymentMethodConfig
    cfg_result = await session.execute(
        select(PaymentMethodConfig).where(
            PaymentMethodConfig.archived == False,  # noqa: E712
        )
    )
    configs = {c.method_id: c for c in cfg_result.scalars().all()}

    visible: list[dict] = []
    for m in methods:
        mtype = m.get("type")
        cfg = None
        if mtype == "manual":
            cfg = configs.get(m["name"])
            if not cfg or not cfg.is_active:
                continue
        elif mtype == "manual_crypto":
            cfg = configs.get(m["name"])
            if not cfg or not cfg.is_active or not (cfg.wallet_address or "").strip():
                continue
        # Attach the owner-defined configuration so the client can render the
        # method's description, information and input fields dynamically.
        if cfg is not None:
            m = {**m, "config": cfg.to_dict()}
        visible.append(m)

    # Owner-created configuration-driven methods (e.g. "inwi_money") are not
    # in the hardcoded registry. They are offered to clients as manual methods
    # with their full owner-defined configuration — no code change needed.
    for method_id, cfg in configs.items():
        if not cfg.is_active:
            continue
        if any(m["name"] == method_id for m in visible):
            continue
        if cfg.method_type not in ("manual", "manual_crypto"):
            continue
        if cfg.method_type == "manual_crypto" and not (cfg.wallet_address or "").strip():
            continue
        visible.append({
            "name": method_id,
            "display_name": cfg.display_name,
            "type": cfg.method_type,
            "category": "local_cash" if cfg.method_type == "manual" else "crypto",
            "is_manual": True,
            "config": cfg.to_dict(),
        })

    # Rebuild grouped output from the visible (gated) methods only
    from billing.registry import PAYMENT_CATEGORIES
    grouped: dict[str, list[dict]] = {cat["key"]: [] for cat in PAYMENT_CATEGORIES}
    grouped["other"] = []
    for m in visible:
        cat = m.get("category", "other")
        if cat in grouped:
            grouped[cat].append(m)

    return {
        "currency": currency_upper,
        "methods": visible,
        "grouped": grouped,
        "categories": [
            {"key": "card_bank", "label": "Card / Bank"},
            {"key": "digital", "label": "Digital Payments"},
            {"key": "local_cash", "label": "Local Cash"},
            {"key": "crypto", "label": "Crypto"},
        ],
    }


# ---------------------------------------------------------------------------
# POST /client/checkout — create checkout session
# ---------------------------------------------------------------------------

@router.post("/checkout")
async def create_checkout(
    body: CheckoutRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Create a checkout session for a plan purchase.

    Flow:
    1. Validate plan exists and is not archived
    2. Validate currency
    3. Validate payment method supports the currency
    4. Calculate price server-side
    5. Validate coupon (if provided)
    6. Check no active subscription for this plan
    7. Create Payment + PENDING Subscription + provider checkout
    8. Return checkout info

    IMPORTANT: No subscription is activated here.
    Activation happens ONLY after confirmed payment via webhook,
    manual approval, or confirm_payment().
    """
    try:
        # 1. Validate plan
        plan = await session.get(PlanDefinition, body.plan_id)
        if not plan:
            raise HTTPException(404, "Plan not found")
        if plan.is_archived:
            raise HTTPException(400, "Plan is no longer available")

        # 2. Validate currency
        currency = body.currency.upper()
        ALL_VALID_CURRENCIES = VALID_CURRENCIES | {"BTC", "ETH", "SOL", "USDT"}
        if currency not in ALL_VALID_CURRENCIES:
            raise HTTPException(400, f"Invalid currency: {currency}")

        # 3. Validate payment method supports the currency
        from billing.registry import get_registry, PAYMENT_METHODS
        registry = get_registry()
        method_name = body.payment_method

        # Owner-created configuration-driven methods (e.g. "inwi_money") are
        # NOT in the hardcoded registry. They are fully supported: the owner
        # defines them in the payment-methods configurator, and the client
        # renders their description/information/fields dynamically.
        owner_cfg = None
        if method_name not in PAYMENT_METHODS:
            from database.models import PaymentMethodConfig
            cfg_result = await session.execute(
                select(PaymentMethodConfig).where(
                    PaymentMethodConfig.method_id == method_name,
                    PaymentMethodConfig.is_active == True,  # noqa: E712
                    PaymentMethodConfig.archived == False,  # noqa: E712
                )
            )
            owner_cfg = cfg_result.scalar_one_or_none()
            if not owner_cfg:
                raise HTTPException(400, f"Unknown payment method: {method_name}")
            method_info = {
                "name": method_name,
                "display_name": owner_cfg.display_name,
                "type": "manual",
                "category": "local_cash",
                "supported_currencies": set(owner_cfg.currencies or ["MAD", "USD", "EUR"]),
            }
        else:
            method_info = PAYMENT_METHODS[method_name]

        # Crypto methods use their own ticker as currency, not USD/EUR/MAD
        if method_info["category"] == "crypto":
            if currency not in method_info["supported_currencies"]:
                raise HTTPException(
                    400,
                    f"{method_info['display_name']} requires currency "
                    f"{', '.join(sorted(method_info['supported_currencies']))}. "
                    f"Select the crypto currency instead of {currency}.",
                )
            # Validate network selection for crypto
            if method_info.get("requires_network_selection"):
                if not body.network:
                    raise HTTPException(
                        400,
                        f"Network selection is required for {method_info['display_name']}. "
                        f"Available: {', '.join(n['id'] for n in method_info.get('networks', []))}",
                    )
                valid_networks = [n["id"] for n in method_info.get("networks", [])]
                if body.network not in valid_networks:
                    raise HTTPException(
                        400,
                        f"Invalid network '{body.network}' for {method_info['display_name']}. "
                        f"Available: {', '.join(valid_networks)}",
                    )
        else:
            if currency not in method_info["supported_currencies"]:
                raise HTTPException(
                    400,
                    f"{method_info['display_name']} does not support {currency}. "
                    f"Supported: {', '.join(sorted(method_info['supported_currencies']))}",
                )

        # Get provider
        provider = registry.get_provider(method_name)
        if provider is None:
            raise HTTPException(500, "Payment provider unavailable")

        if not provider.is_configured:
            raise HTTPException(
                503,
                f"{method_info['display_name']} is not configured. "
                "Please contact support.",
            )

        # 4. Calculate price server-side
        original_price = await get_plan_price(plan, currency)
        if original_price is None:
            raise HTTPException(400, f"Plan does not support {currency} pricing")

        # 5. Validate coupon
        coupon = None
        discount_amount = Decimal("0")
        final_price = original_price

        if body.coupon_code and body.coupon_code.strip():
            try:
                coupon, original_price_val, discount_amount, final_price = (
                    await validate_coupon_for_purchase(
                        session,
                        code=body.coupon_code.strip(),
                        user_id=user.id,
                        plan=plan,
                        currency=currency,
                    )
                )
            except CouponValidationError as e:
                raise HTTPException(e.status_code, e.message)

        # 6. Check for existing ACTIVE subscription for this plan
        existing = await session.execute(
            select(Subscription).where(
                Subscription.user_id == user.id,
                Subscription.plan == body.plan_id,
                Subscription.active == True,  # noqa: E712
                Subscription.status == "ACTIVE",
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(409, "You already have an active subscription for this plan")

        # 7. Build URLs
        base_url = os.getenv("APP_BASE_URL", "http://localhost:3000")
        success_url = body.success_url or f"{base_url}/dashboard/subscription?payment=success"
        cancel_url = body.cancel_url or f"{base_url}/dashboard/subscription?payment=cancelled"

        # 8. Determine payment method type
        payment_method_type = method_info.get("type", "automatic")
        # payment_method_type can be: automatic, manual, manual_crypto

        # 8b. For manual/manual_crypto methods the Owner config is REQUIRED
        # (REQ 4/5/10): the client must see the owner's real instructions and
        # wallet — never a hardcoded template or a placeholder address.
        owner_config = None
        if payment_method_type in ("manual", "manual_crypto"):
            from database.models import PaymentMethodConfig
            if owner_cfg is not None:
                cfg = owner_cfg
            else:
                cfg_result = await session.execute(
                    select(PaymentMethodConfig).where(
                        PaymentMethodConfig.method_id == method_name,
                        PaymentMethodConfig.is_active == True,  # noqa: E712
                        PaymentMethodConfig.archived == False,  # noqa: E712
                    )
                )
                cfg = cfg_result.scalar_one_or_none()
            if not cfg:
                raise HTTPException(
                    503,
                    f"{method_info['display_name']} is not configured yet. Please contact support.",
                )
            owner_config = cfg.to_dict()
            if payment_method_type == "manual_crypto" and not (cfg.wallet_address or "").strip():
                raise HTTPException(
                    503,
                    f"{method_info['display_name']} is not configured yet. Please contact support.",
                )

        # 9. Create checkout
        svc = _get_payment_service_for_method(method_name)
        result = await svc.create_checkout(
            session,
            user=user,
            plan=plan,
            currency=currency,
            coupon=coupon,
            original_price=original_price,
            discount_amount=discount_amount,
            final_price=final_price,
            success_url=success_url,
            cancel_url=cancel_url,
            payment_method_type=payment_method_type,
            manual_instructions=None,
            owner_config=owner_config,
        )

        await session.commit()

        return {
            "success": True,
            "checkout": result,
            "payment_method": {
                "name": method_name,
                "display_name": method_info["display_name"],
                "type": payment_method_type,
            },
        }
    except HTTPException:
        raise
    except PaymentServiceError as e:
        raise HTTPException(e.status_code, str(e))
    except Exception as e:
        logger.exception("Checkout creation failed")
        await session.rollback()
        raise HTTPException(500, "Failed to create checkout")


# ---------------------------------------------------------------------------
# POST /client/payments/{payment_id}/submit — submit manual payment
# ---------------------------------------------------------------------------

@router.post("/payments/{payment_id}/submit")
async def submit_manual_payment(
    payment_id: str,
    body: ManualPaymentSubmitRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Client submits a manual payment for verification.

    Transitions PENDING → PENDING_VERIFICATION.
    """
    svc = _get_payment_service_for_method("manual")
    try:
        from datetime import datetime as _dt
        payment_date = None
        if body.payment_date:
            try:
                payment_date = _dt.fromisoformat(body.payment_date.replace("Z", "+00:00"))
            except ValueError:
                raise HTTPException(400, "Invalid payment_date — use ISO 8601 format")
        result = await svc.submit_manual_payment(
            session,
            payment_id=payment_id,
            user_id=user.id,
            manual_reference=body.manual_reference,
            manual_proof_url=body.manual_proof_url,
            payer_name=body.payer_name,
            payer_phone=body.payer_phone,
            payment_date=payment_date,
            amount_paid=Decimal(str(body.amount_paid)) if body.amount_paid is not None else None,
            client_fields_data=body.client_fields_data,
        )
        await session.commit()
        return {"success": True, "payment": result}
    except PaymentServiceError as e:
        raise HTTPException(e.status_code, str(e))


# ---------------------------------------------------------------------------
# POST /client/payments/{payment_id}/submit-crypto — submit crypto proof
# ---------------------------------------------------------------------------

@router.post("/payments/{payment_id}/submit-crypto")
async def submit_crypto_proof(
    payment_id: str,
    body: CryptoProofSubmitRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Client submits crypto payment proof.

    Transitions AWAITING_PAYMENT → TRANSACTION_DETECTED.
    """
    from decimal import Decimal
    svc = _get_payment_service_for_method("manual_crypto")
    try:
        result = await svc.submit_crypto_proof(
            session,
            payment_id=payment_id,
            user_id=user.id,
            tx_hash=body.tx_hash,
            amount_sent=Decimal(str(body.amount_sent)),
            network=body.network,
            screenshot_url=body.screenshot_url,
            note=body.note,
        )
        await session.commit()
        return {"success": True, "payment": result}
    except PaymentServiceError as e:
        raise HTTPException(e.status_code, str(e))


# ---------------------------------------------------------------------------
# POST /client/payments/{payment_id}/upload-proof — real proof file upload
# ---------------------------------------------------------------------------

@router.post("/payments/{payment_id}/upload-proof")
async def upload_payment_proof(
    payment_id: str,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Upload a proof-of-payment file (JPG/JPEG/PNG/PDF, max 10 MB).

    Only the owning user may upload. The file is stored server-side and the
    returned URL is persisted on the payment when the client submits.
    """
    payment = await session.get(Payment, payment_id)
    if not payment:
        raise HTTPException(404, "Payment not found")
    if payment.user_id != user.id:
        raise HTTPException(403, "Access denied")

    # Validate content type + extension (never trust the client alone)
    media_type = (file.content_type or "").lower()
    ext = Path(file.filename or "").suffix.lower()
    if media_type not in ALLOWED_PROOF_MEDIA or ext not in ALLOWED_PROOF_EXTENSIONS:
        raise HTTPException(
            400,
            "Unsupported file type. Accepted: JPG, JPEG, PNG, PDF (max 10 MB)",
        )

    data = await file.read()
    if not data:
        raise HTTPException(400, "Uploaded file is empty")
    if len(data) > MAX_PROOF_BYTES:
        raise HTTPException(400, "File exceeds the 10 MB upload limit")

    # Store with a unique name: <payment_number>-<uuid>.<ext>
    import uuid
    safe_ext = ALLOWED_PROOF_MEDIA[media_type]
    stored_name = f"{payment.payment_number}-{uuid.uuid4().hex[:12]}{safe_ext}"
    try:
        PROOF_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        (PROOF_STORAGE_DIR / stored_name).write_bytes(data)
    except OSError as exc:
        logger.error("proof upload: could not store %s: %s", stored_name, exc)
        raise HTTPException(500, "Could not store proof file on server")

    url = f"/api/client/uploads/proofs/{stored_name}"
    return {"success": True, "url": url, "filename": stored_name, "size_bytes": len(data)}


# ---------------------------------------------------------------------------
# GET /client/uploads/proofs/{filename} — serve an uploaded proof file
# ---------------------------------------------------------------------------

@router.get("/uploads/proofs/{filename}")
async def serve_payment_proof(
    filename: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Serve an uploaded proof file to the owning client.

    The filename embeds the payment number; only the user who owns that
    payment may view it. (Owner/admin viewing is served by the admin route.)
    """
    safe = _safe_proof_filename(filename)
    if safe != filename:
        raise HTTPException(400, "Invalid filename")
    file_path = PROOF_STORAGE_DIR / safe
    if not file_path.exists():
        raise HTTPException(404, "Proof file not found")

    # Filename format: {payment_number}-{hash}.{ext} — the hash is the last
    # dash-separated segment, so the payment number is everything before it.
    stem = safe.rsplit(".", 1)[0]
    parts = stem.split("-")
    payment_number = "-".join(parts[:-1]) if len(parts) > 1 else None
    if payment_number:
        result = await session.execute(
            select(Payment).where(Payment.payment_number == payment_number)
        )
        payment = result.scalars().first()
        if payment and payment.user_id != user.id:
            raise HTTPException(403, "Access denied")

    ext = f".{safe.lower().rsplit('.', 1)[-1]}"
    media_type = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }.get(ext, "application/octet-stream")
    return FileResponse(path=file_path, media_type=media_type)


# ---------------------------------------------------------------------------
# POST /client/webhook/payment — provider webhook handler (generic)
# ---------------------------------------------------------------------------

@router.post("/webhook/payment")
async def payment_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """
    Handle payment provider webhooks.

    Idempotent: duplicate events are safely ignored.
    Signature verification is performed by the provider adapter.
    """
    body = await request.body()
    headers = dict(request.headers)

    # Determine provider from URL path or headers
    # Try to identify provider from common patterns
    from billing.registry import get_registry
    registry = get_registry()
    all_providers = registry.get_all_providers()

    # Try each configured provider's webhook parser
    for name, provider in all_providers.items():
        if provider.is_manual():
            continue
        try:
            event = await provider.parse_webhook_event(
                payload=body,
                headers=headers,
            )
            if event is not None:
                svc = _get_payment_service_for_method(name)
                result = await svc.process_webhook(session, event=event)
                await session.commit()

                if result:
                    logger.info("Webhook processed (%s): %s", name, result)
                    return {"received": True, "processed": True, "result": result}
                else:
                    return {"received": True, "processed": False, "reason": "duplicate_or_ignored"}
        except Exception as e:
            logger.warning("Webhook parsing failed for %s: %s", name, e)
            continue

    # No provider matched — return 200 to acknowledge
    return {"received": True, "processed": False}


# ---------------------------------------------------------------------------
# POST /client/webhook/payment/{provider} — provider-specific webhook handler
# ---------------------------------------------------------------------------

@router.post("/webhook/payment/{provider_name}")
async def payment_webhook_provider(
    provider_name: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Handle webhook for a specific provider."""
    body = await request.body()
    headers = dict(request.headers)

    from billing.registry import get_registry
    registry = get_registry()
    provider = registry.get_provider(provider_name)

    if provider is None or provider.is_manual():
        return {"received": True, "processed": False, "reason": "unknown_provider"}

    event = await provider.parse_webhook_event(
        payload=body,
        headers=headers,
    )

    if event is None:
        return {"received": True, "processed": False}

    svc = _get_payment_service_for_method(provider_name)
    result = await svc.process_webhook(session, event=event)
    await session.commit()

    if result:
        logger.info("Webhook processed (%s): %s", provider_name, result)
        return {"received": True, "processed": True, "result": result}
    return {"received": True, "processed": False, "reason": "duplicate_or_ignored"}


# ---------------------------------------------------------------------------
# GET /client/payments — payment history
# ---------------------------------------------------------------------------

@router.get("/payments")
async def payment_history(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    limit: int = 50,
    offset: int = 0,
):
    """Get payment history for the current user."""
    # Sweep stale payments first so expired ones surface as EXPIRED (REQ 7)
    svc = _get_payment_service_for_method("manual")
    await svc.expire_stale_payments(session)

    result = await session.execute(
        select(Payment)
        .where(Payment.user_id == user.id)
        .order_by(Payment.created_at.desc())
        .limit(min(limit, 100))
        .offset(offset)
    )
    payments = list(result.scalars().all())

    # Get total count
    count_result = await session.execute(
        select(func.count()).select_from(Payment).where(Payment.user_id == user.id)
    )
    total = count_result.scalar() or 0

    return {
        "payments": [p.to_dict() for p in payments],
        "total": total,
    }


# ---------------------------------------------------------------------------
# GET /client/payments/{payment_id} — single payment detail
# ---------------------------------------------------------------------------

@router.get("/payments/{payment_id}")
async def payment_detail(
    payment_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Get a single payment by ID (owner only)."""
    payment = await session.get(Payment, payment_id)
    if not payment:
        raise HTTPException(404, "Payment not found")
    if payment.user_id != user.id:
        raise HTTPException(403, "Access denied")
    return {"payment": payment.to_dict()}


# ---------------------------------------------------------------------------
# POST /client/payments/{payment_id}/cancel — cancel pending payment
# ---------------------------------------------------------------------------

@router.post("/payments/{payment_id}/cancel")
async def cancel_payment(
    payment_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Cancel a PENDING payment."""
    svc = _get_payment_service_for_method("stripe")
    try:
        result = await svc.cancel_payment(
            session,
            payment_id=payment_id,
            user_id=user.id,
        )
        await session.commit()
        return {"success": True, "payment": result}
    except PaymentServiceError as e:
        raise HTTPException(e.status_code, str(e))


# ---------------------------------------------------------------------------
# GET /client/receipts — receipt list
# ---------------------------------------------------------------------------

@router.get("/receipts")
async def receipt_list(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    limit: int = 50,
    offset: int = 0,
):
    """Get receipts for the current user."""
    receipts = await ReceiptService.get_receipts_for_user(
        session,
        user_id=user.id,
        limit=min(limit, 100),
        offset=offset,
    )
    return {
        "receipts": [r.to_dict() for r in receipts],
    }


# ---------------------------------------------------------------------------
# GET /client/receipts/{receipt_number} — single receipt
# ---------------------------------------------------------------------------

@router.get("/receipts/{receipt_number}")
async def receipt_detail(
    receipt_number: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Get a receipt by its receipt number."""
    receipt = await ReceiptService.get_receipt_by_number(
        session,
        receipt_number=receipt_number,
    )
    if not receipt:
        raise HTTPException(404, "Receipt not found")
    if receipt.user_id != user.id:
        raise HTTPException(403, "Access denied")
    return {"receipt": receipt.to_dict()}


# ---------------------------------------------------------------------------
# GET /client/checkout/status — check checkout status
# ---------------------------------------------------------------------------

@router.get("/checkout/status/{payment_id}")
async def checkout_status(
    payment_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Check the status of a checkout/payment.

    Client polls this after redirecting from provider checkout
    or after submitting manual payment reference.
    """
    payment = await session.get(Payment, payment_id)
    if not payment:
        raise HTTPException(404, "Payment not found")
    if payment.user_id != user.id:
        raise HTTPException(403, "Access denied")

    # Get linked subscription status if exists
    sub_status = None
    if payment.subscription_id:
        sub = await session.get(Subscription, payment.subscription_id)
        if sub:
            sub_status = {
                "status": sub.status,
                "active": sub.active,
                "subscription_number": sub.subscription_number,
            }

    # Get receipt if payment is PAID
    receipt_data = None
    if payment.status == "PAID":
        receipt = await ReceiptService.get_receipt_for_payment(
            session, payment_id=payment.id,
        )
        if receipt:
            receipt_data = receipt.to_dict()

    return {
        "payment": payment.to_dict(),
        "subscription": sub_status,
        "receipt": receipt_data,
    }


# ---------------------------------------------------------------------------
# GET /client/provider/status — check all payment provider statuses
# ---------------------------------------------------------------------------

@router.get("/provider/status")
async def provider_status(
    user: User = Depends(get_current_user),
):
    """Check status of all payment providers."""
    from billing.registry import get_registry
    registry = get_registry()
    return {
        "providers": registry.get_provider_status_all(),
    }

"""Owner/Admin payment method configuration endpoints."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import get_session
from database.models import PaymentMethodConfig
from security.auth import get_current_admin_user, require_permission, Permission

router = APIRouter(tags=["admin", "payment-configs"])

# Fields editable for manual methods (beneficiary/account details).
MANUAL_FIELDS = [
    "display_name", "beneficiary_name", "account_rib", "phone_number",
    "branch", "instructions", "reference_instructions",
    "reference_required", "required_fields", "optional_fields",
    "wallet_address", "network", "expires_hours",
    "description", "information", "client_fields", "receipt_required",
    "is_active", "display_order",
]

# Fields editable for automatic methods (enable/disable/order/name + gateway info).
AUTOMATIC_FIELDS = [
    "display_name", "is_active", "display_order",
    "description", "currencies", "provider_name", "gateway_status",
]

# Fields editable for manual_crypto methods (owner wallet + expiry).
CRYPTO_FIELDS = [
    "display_name", "instructions", "reference_instructions",
    "reference_required", "required_fields", "optional_fields",
    "wallet_address", "network", "expires_hours",
    "description", "information", "client_fields", "receipt_required",
    "is_active", "display_order",
]


@router.get("/payment-configs")
async def list_payment_configs(
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission(Permission.BILLING_READ)),
):
    """List all non-archived payment method configurations."""
    result = await session.execute(
        select(PaymentMethodConfig)
        .where(PaymentMethodConfig.archived == False)  # noqa: E712
        .order_by(PaymentMethodConfig.display_order, PaymentMethodConfig.method_id)
    )
    configs = result.scalars().all()
    return {"configs": [c.to_dict() for c in configs]}


@router.get("/payment-configs/{method_id}")
async def get_payment_config(
    method_id: str,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission(Permission.BILLING_READ)),
):
    """Get a single payment method configuration."""
    result = await session.execute(select(PaymentMethodConfig).where(PaymentMethodConfig.method_id == method_id))
    config = result.scalar_one_or_none()
    if not config or config.archived:
        raise HTTPException(404, "Payment method config not found")
    return config.to_dict()


@router.post("/payment-configs")
async def create_payment_config(
    body: dict,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission(Permission.BILLING_CREATE)),
):
    """Create a new manual payment method configuration."""
    method_id = (body.get("method_id") or "").strip().lower()
    if not method_id:
        raise HTTPException(400, "method_id is required")
    if not method_id.replace("_", "").isalnum():
        raise HTTPException(400, "method_id must contain only letters, digits and underscores")

    display_name = (body.get("display_name") or "").strip()
    if not display_name:
        raise HTTPException(400, "display_name is required")

    existing = await session.execute(select(PaymentMethodConfig).where(PaymentMethodConfig.method_id == method_id))
    if existing.scalar_one_or_none():
        raise HTTPException(409, f"Payment method '{method_id}' already exists")

    config = PaymentMethodConfig(
        method_id=method_id,
        method_type="manual",
        display_name=display_name,
        beneficiary_name=body.get("beneficiary_name"),
        account_rib=body.get("account_rib"),
        phone_number=body.get("phone_number"),
        branch=body.get("branch"),
        instructions=body.get("instructions"),
        reference_instructions=body.get("reference_instructions"),
        reference_required=bool(body.get("reference_required", True)),
        required_fields=body.get("required_fields"),
        optional_fields=body.get("optional_fields"),
        wallet_address=body.get("wallet_address"),
        network=body.get("network"),
        expires_hours=int(body.get("expires_hours", 72) or 72),
        description=body.get("description"),
        information=body.get("information"),
        client_fields=body.get("client_fields"),
        receipt_required=bool(body.get("receipt_required", True)),
        currencies=body.get("currencies"),
        provider_name=body.get("provider_name"),
        gateway_status=body.get("gateway_status"),
        is_active=bool(body.get("is_active", True)),
        display_order=int(body.get("display_order", 0) or 0),
    )
    session.add(config)
    await session.commit()
    return {"success": True, "config": config.to_dict()}


@router.put("/payment-configs/{method_id}")
async def update_payment_config(
    method_id: str,
    body: dict,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission(Permission.BILLING_CREATE)),
):
    """Create or update a payment method configuration."""
    result = await session.execute(select(PaymentMethodConfig).where(PaymentMethodConfig.method_id == method_id))
    config = result.scalar_one_or_none()

    if not config:
        config = PaymentMethodConfig(method_id=method_id, display_name=body.get("display_name", method_id))
        session.add(config)

    if config.archived:
        raise HTTPException(400, "Archived payment methods cannot be edited")

    # Automatic methods only allow enable/disable/order/name — never manual fields.
    if config.method_type == "manual_crypto":
        allowed = CRYPTO_FIELDS
    else:
        allowed = MANUAL_FIELDS if config.method_type == "manual" else AUTOMATIC_FIELDS
    for field in allowed:
        if field in body:
            setattr(config, field, body[field])

    # Sanity: expiry must be a positive integer
    if "expires_hours" in body and body["expires_hours"] is not None:
        try:
            config.expires_hours = max(1, int(body["expires_hours"]))
        except (TypeError, ValueError):
            raise HTTPException(400, "expires_hours must be a positive integer")

    config.updated_at = datetime.now(timezone.utc)
    await session.commit()
    return {"success": True, "config": config.to_dict()}


@router.delete("/payment-configs/{method_id}")
async def archive_payment_config(
    method_id: str,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission(Permission.BILLING_CREATE)),
):
    """Archive (soft-delete) a payment method configuration."""
    result = await session.execute(select(PaymentMethodConfig).where(PaymentMethodConfig.method_id == method_id))
    config = result.scalar_one_or_none()
    if not config or config.archived:
        raise HTTPException(404, "Payment method config not found")

    config.archived = True
    config.is_active = False
    config.updated_at = datetime.now(timezone.utc)
    await session.commit()
    return {"success": True, "archived": method_id}
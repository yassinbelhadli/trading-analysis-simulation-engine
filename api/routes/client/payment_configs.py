"""Client-readable payment method configurations."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import get_session
from database.models import PaymentMethodConfig
from security.auth import get_current_user

router = APIRouter(tags=["client", "payment-configs"])


@router.get("/payment-configs")
async def list_active_payment_configs(
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    """List active payment method configurations for clients.

    Returns the full owner-defined configuration for each active method:
    description, structured information blocks, client input field
    definitions, receipt requirement, and display order. The client UI
    renders forms dynamically from this data — nothing is hardcoded.
    """
    result = await session.execute(
        select(PaymentMethodConfig)
        .where(PaymentMethodConfig.is_active == True)  # noqa: E712
        .order_by(PaymentMethodConfig.display_order)
    )
    configs = result.scalars().all()
    return {"configs": [c.to_dict() for c in configs]}


@router.get("/payment-configs/{method_id}")
async def get_active_payment_config(
    method_id: str,
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
):
    """Get a single active payment method configuration for clients."""
    result = await session.execute(
        select(PaymentMethodConfig).where(
            PaymentMethodConfig.method_id == method_id,
            PaymentMethodConfig.is_active == True,  # noqa: E712
            PaymentMethodConfig.archived == False,  # noqa: E712
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(404, "Payment method config not found")
    return config.to_dict()
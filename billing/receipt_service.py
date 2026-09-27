"""
Receipt service — generates and retrieves receipts for successful payments.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Payment, Receipt

logger = logging.getLogger(__name__)


class ReceiptService:
    """Handles receipt generation and retrieval."""

    @staticmethod
    async def get_receipt_for_payment(
        session: AsyncSession,
        *,
        payment_id: str,
    ) -> Optional[Receipt]:
        """Get the receipt for a specific payment."""
        result = await session.execute(
            select(Receipt).where(Receipt.payment_id == payment_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_receipts_for_user(
        session: AsyncSession,
        *,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Receipt]:
        """Get all receipts for a user, newest first."""
        result = await session.execute(
            select(Receipt)
            .where(Receipt.user_id == user_id)
            .order_by(Receipt.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_receipt_by_number(
        session: AsyncSession,
        *,
        receipt_number: str,
    ) -> Optional[Receipt]:
        """Get a receipt by its human-readable number."""
        result = await session.execute(
            select(Receipt).where(Receipt.receipt_number == receipt_number)
        )
        return result.scalar_one_or_none()

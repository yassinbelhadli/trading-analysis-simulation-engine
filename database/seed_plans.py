"""
Seed default plans with multi-currency prices (USD / EUR / MAD).

Idempotent: existing plans are updated with the canonical pricing/features,
missing plans are created. Safe to run repeatedly.

Usage:
    python -m database.seed_plans
"""

import asyncio
import logging

from sqlalchemy import select

from database.db import async_session_factory, engine
from database.models import PlanDefinition

logger = logging.getLogger(__name__)

DEFAULT_FEATURES: dict = {
    "mt5_access": True,
    "trading_engine": True,
    "economic_calendar": True,
    "news": True,
    "telegram_notifications": True,
    "download_center": True,
    "mt5_account_limit": 3,
}

DEFAULT_PLANS: list[dict] = [
    {
        "id": "15_days",
        "name": "15 Days",
        "price_usd": 12,
        "price_eur": 10,
        "price_mad": 100,
        "duration_days": 15,
        "display_order": 1,
    },
    {
        "id": "30_days",
        "name": "30 Days",
        "price_usd": 22,
        "price_eur": 18,
        "price_mad": 180,
        "duration_days": 30,
        "display_order": 2,
    },
]


async def seed_plans() -> dict:
    """Create or update the default plans. Returns a summary dict."""
    created, updated = [], []
    async with async_session_factory() as session:
        for spec in DEFAULT_PLANS:
            result = await session.execute(
                select(PlanDefinition).where(PlanDefinition.id == spec["id"])
            )
            plan = result.scalar_one_or_none()
            if plan is None:
                plan = PlanDefinition(id=spec["id"])
                session.add(plan)
                created.append(spec["id"])
            else:
                updated.append(spec["id"])

            plan.name = spec["name"]
            plan.price_usd = spec["price_usd"]
            plan.price_eur = spec["price_eur"]
            plan.price_mad = spec["price_mad"]
            plan.duration_days = spec["duration_days"]
            plan.features_json = DEFAULT_FEATURES
            plan.display_order = spec["display_order"]

        await session.commit()

    summary = {"created": created, "updated": updated}
    logger.info("Plan seed complete: %s", summary)
    return summary


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    try:
        await seed_plans()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

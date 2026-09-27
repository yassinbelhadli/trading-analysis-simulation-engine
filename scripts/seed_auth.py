"""
Seed the database with built-in roles, permissions, and a default admin user.

Usage:
    python -m scripts.seed_auth

Safe to re-run — upserts roles/permissions and skips existing admin user.
"""
from __future__ import annotations

import asyncio
import getpass
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from database.db import async_session_factory
from database.models import Role, User
from security.auth import hash_password, seed_roles_and_permissions

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


async def seed():
    async with async_session_factory() as session:
        await seed_roles_and_permissions(session)

        admin_email = os.getenv("ADMIN_EMAIL", "").strip() or "admin@ictfunded.com"
        admin_password = os.getenv("ADMIN_PASSWORD", "").strip()

        result = await session.execute(select(User).where(User.email == admin_email))
        existing = result.scalar_one_or_none()

        if existing:
            logger.info(f"Admin user already exists: {admin_email}")
            return

        if not admin_password:
            admin_password = getpass.getpass("Enter admin password: ")

        result = await session.execute(select(Role).where(Role.name == "owner"))
        owner_role = result.scalar_one_or_none()

        user = User(
            email=admin_email,
            password_hash=hash_password(admin_password),
            first_name="Super",
            last_name="Admin",
            role_id=owner_role.id if owner_role else None,
            language="EN",
            status="active",
            account_status="active",
            email_verified=True,
        )
        session.add(user)
        await session.commit()
        logger.info(f"Created admin user: {admin_email}")


if __name__ == "__main__":
    asyncio.run(seed())

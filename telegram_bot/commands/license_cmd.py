from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from database.db import async_session_factory
from database.models import License, User
from sqlalchemy import select
from telegram_bot.ui.trade_messages import format_license_info

logger = logging.getLogger(__name__)


async def license_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return

    async with async_session_factory() as session:
        result = await session.execute(select(User).where(User.telegram_id == user.id))
        db_user = result.scalar_one_or_none()
        if not db_user:
            await update.message.reply_text("Account not found. Use /start to register.")
            return

        lic_result = await session.execute(
            select(License).where(License.user_id == db_user.id).order_by(License.created_at.desc())
        )
        licenses = list(lic_result.scalars().all())

    if not licenses:
        await update.message.reply_text("🔑 No licenses found.")
        return

    for lic in licenses:
        text = format_license_info(
            license_key=lic.license_key,
            plan=lic.plan.title(),
            status=lic.status,
            expires_at=lic.expires_at.strftime("%Y-%m-%d") if lic.expires_at else None,
            max_accounts=lic.max_accounts,
            bound_accounts=1 if lic.bound_account_id else 0,
        )
        await update.message.reply_text(text)

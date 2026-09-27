from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes
from sqlalchemy import select

from database.db import async_session_factory
from database.models import PaperTrade, User
from telegram_bot.ui.trade_messages import format_open_trades

logger = logging.getLogger(__name__)


async def open_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return

    async with async_session_factory() as session:
        result = await session.execute(select(User).where(User.telegram_id == user.id))
        db_user = result.scalar_one_or_none()
        if not db_user:
            await update.message.reply_text("Account not found. Use /start to register.")
            return

        trades_result = await session.execute(
            select(PaperTrade).where(
                PaperTrade.user_id == db_user.id,
                PaperTrade.status.in_(["PLANNED", "FILLED"]),
            )
        )
        trades = list(trades_result.scalars().all())

    trade_list = []
    for t in trades:
        trade_list.append({
            "symbol": t.symbol,
            "direction": t.direction,
            "entry_price": t.entry_price,
            "unrealized_pnl": 0,
        })

    text = format_open_trades(trade_list)
    await update.message.reply_text(text)

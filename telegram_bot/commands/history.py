from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes
from sqlalchemy import select, desc

from database.db import async_session_factory
from database.models import PaperTrade, User

logger = logging.getLogger(__name__)


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
                PaperTrade.status == "CLOSED",
            ).order_by(desc(PaperTrade.closed_at)).limit(10)
        )
        trades = list(trades_result.scalars().all())

    if not trades:
        await update.message.reply_text("📭 No trade history.")
        return

    lines = ["📋 Recent Trades", ""]
    for i, t in enumerate(trades, 1):
        icon = "🟢" if t.direction == "BUY" else "🔴"
        pnl = t.realized_pnl or 0
        pnl_str = f"{'+' if pnl >= 0 else ''}${pnl:.2f}"
        r_str = f"({'+' if (t.realized_r or 0) >= 0 else ''}{t.realized_r:.2f}R)" if t.realized_r else ""
        date = t.closed_at.strftime("%m/%d") if t.closed_at else ""
        lines.append(f"{i}. {icon} {t.symbol} {t.direction}")
        lines.append(f"   {pnl_str} {r_str} {date}")
        lines.append("")

    await update.message.reply_text("\n".join(lines))

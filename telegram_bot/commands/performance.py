from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from database.db import async_session_factory
from database.models import PaperTrade, User
from sqlalchemy import select
from telegram_bot.ui.trade_messages import format_performance_summary

logger = logging.getLogger(__name__)


async def performance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            )
        )
        trades = list(trades_result.scalars().all())

    if not trades:
        await update.message.reply_text("No trades yet.")
        return

    wins = sum(1 for t in trades if t.realized_pnl and t.realized_pnl > 0)
    losses = sum(1 for t in trades if t.realized_pnl and t.realized_pnl < 0)
    net_pnl = sum(t.realized_pnl for t in trades)
    win_rate = wins / len(trades) * 100 if trades else 0
    gw = sum(t.realized_pnl for t in trades if t.realized_pnl and t.realized_pnl > 0)
    gl = abs(sum(t.realized_pnl for t in trades if t.realized_pnl and t.realized_pnl < 0))
    pf = round(gw / gl, 2) if gl > 0 else (gw if gw else 0)
    r_vals = [t.realized_r for t in trades if t.realized_r is not None]
    avg_r = round(sum(r_vals) / len(r_vals), 2) if r_vals else 0

    from datetime import datetime, timezone
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_pnl = sum(t.realized_pnl for t in trades if t.closed_at and t.closed_at >= today_start)

    by_sym = {}
    for t in trades:
        sym = t.symbol or "?"
        if sym not in by_sym:
            by_sym[sym] = 0
        by_sym[sym] += t.realized_pnl or 0
    best_sym = max(by_sym, key=by_sym.get) if by_sym else ""

    text = format_performance_summary(
        total_trades=len(trades),
        wins=wins,
        losses=losses,
        win_rate=win_rate,
        net_pnl=net_pnl,
        profit_factor=pf,
        avg_r=avg_r,
        best_symbol=best_sym,
        today_pnl=today_pnl,
    )
    await update.message.reply_text(text)

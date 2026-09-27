from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func

from database.db import async_session_factory
from database.models import PaperTrade, User

logger = logging.getLogger(__name__)


async def generate_user_summary(user_id: str, since: datetime) -> str:
    """Build a professional daily/weekly report string."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(PaperTrade).where(
                PaperTrade.user_id == user_id,
                PaperTrade.status == "CLOSED",
                PaperTrade.closed_at >= since,
            )
        )
        trades = list(result.scalars().all())

    if not trades:
        return ""

    total = len(trades)
    wins = sum(1 for t in trades if t.realized_pnl and t.realized_pnl > 0)
    losses = sum(1 for t in trades if t.realized_pnl and t.realized_pnl < 0)
    net_pnl = sum(t.realized_pnl for t in trades if t.realized_pnl)
    win_rate = wins / total * 100 if total else 0

    # By-symbol breakdown
    by_sym: dict[str, list[float]] = {}
    for t in trades:
        sym = t.symbol or "?"
        by_sym.setdefault(sym, []).append(t.realized_pnl or 0)

    best_sym, best_pnl = "", float("-inf")
    worst_sym, worst_pnl = "", float("inf")
    for sym, pnls in by_sym.items():
        total_sym = sum(pnls)
        if total_sym > best_pnl:
            best_sym, best_pnl = sym, total_sym
        if total_sym < worst_pnl:
            worst_sym, worst_pnl = sym, total_sym

    lines = [
        "\U0001f4c8 <b>Daily Report</b>",
        "",
        f"Signals: <b>{total}</b>",
        f"Trades: <b>{total}</b>",
        f"Wins: <b>{wins}</b>",
        f"Losses: <b>{losses}</b>",
        f"Win Rate: <b>{win_rate:.0f}%</b>",
        f"PnL: <b>{'+' if net_pnl >= 0 else ''}${net_pnl:.2f}</b>",
    ]
    if best_sym:
        lines.append(f"Best: <b>{best_sym}</b> ({'+' if best_pnl >= 0 else ''}${best_pnl:.2f})")
    if worst_sym:
        lines.append(f"Worst: <b>{worst_sym}</b> ({'+' if worst_pnl >= 0 else ''}${worst_pnl:.2f})")

    return "\n".join(lines)


async def send_daily_summaries(bot):
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=24)
    await _send_summaries(bot, since, "\U0001f4c8 <b>Daily Report</b>")


async def send_weekly_summaries(bot):
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=7)
    await _send_summaries(bot, since, "\U0001f4c8 <b>Weekly Report</b>", pref_key="weekly_report")


async def send_monthly_summaries(bot):
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=30)
    await _send_summaries(bot, since, "\U0001f4c8 <b>Monthly Report</b>", pref_key="monthly_report")


def _notif_pref(user, key: str, default: bool = True) -> bool:
    prefs = user.preferences or {}
    notifs = prefs.get("notifications") or {}
    if isinstance(notifs, dict) and key in notifs:
        return bool(notifs[key])
    return default


async def _send_summaries(bot, since: datetime, header: str, pref_key: str | None = None):
    async with async_session_factory() as session:
        result = await session.execute(
            select(User).where(User.telegram_id.isnot(None))
        )
        users = list(result.scalars().all())

    sent = 0
    for user in users:
        if pref_key is not None and not _notif_pref(user, pref_key):
            continue
        text = await generate_user_summary(user.id, since)
        if text:
            try:
                await bot.send_message(
                    chat_id=int(user.telegram_id),
                    text=text,
                    parse_mode="HTML",
                )
                sent += 1
            except Exception as e:
                logger.warning("Failed to send report to %s: %s", user.id, e)

    logger.info("Report sent to %d/%d users", sent, len(users))

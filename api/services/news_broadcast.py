from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import async_session_factory
from database.models import NewsEvent

logger = logging.getLogger(__name__)

CSV_PATH = Path(__file__).resolve().parents[2] / "data" / "processed" / "news_cache.csv"

# Track which events we've already alerted about (in-memory set)
_alerted_news_ids: set[str] = set()


async def sync_csv_to_db():
    """Read the CSV news cache and sync new/updated events to the database."""
    if not CSV_PATH.exists():
        return 0, 0

    import pandas as pd

    df = pd.read_csv(CSV_PATH)
    if df.empty:
        return 0, 0

    total = len(df)
    created = 0
    updated = 0

    async with async_session_factory() as session:
        for _, row in df.iterrows():
            news_id = str(row.get("news_id", ""))
            if not news_id:
                continue

            # Check if exists
            existing = (
                await session.execute(select(NewsEvent).where(NewsEvent.news_id == news_id))
            ).scalar_one_or_none()

            data = {
                "news_id": news_id,
                "time": _parse_dt(row.get("time")),
                "currency": str(row.get("currency", "USD")),
                "event": str(row.get("event", "")),
                "impact": str(row.get("impact", "LOW")),
                "actual": _str_or_none(row.get("actual")),
                "forecast": _str_or_none(row.get("forecast")),
                "previous": _str_or_none(row.get("previous")),
                "status": str(row.get("status", "UPCOMING")),
                "version": _safe_int(row.get("version"), 1),
                "first_seen": _parse_dt(row.get("first_seen")),
                "last_checked": _parse_dt(row.get("last_checked")),
                "updated_at": _parse_dt(row.get("updated_at")),
                "processed": _safe_bool(row.get("processed")),
                "analyzed": _safe_bool(row.get("analyzed")),
                "telegram_sent": _safe_bool(row.get("telegram_sent")),
                "entry_processed": _safe_bool(row.get("entry_processed")),
            }

            if existing:
                for k, v in data.items():
                    if k != "news_id":
                        setattr(existing, k, v)
                updated += 1
            else:
                session.add(NewsEvent(**data))
                created += 1

        await session.commit()

    logger.info("CSV→DB sync: %d created, %d updated (of %d total)", created, updated, total)
    return created, updated


async def check_and_alert_upcoming_events():
    """Check for upcoming high-impact USD events and send alerts."""
    now = datetime.now(timezone.utc)
    window_end = now + timedelta(hours=2)

    async with async_session_factory() as session:
        result = await session.execute(
            select(NewsEvent).where(
                NewsEvent.currency == "USD",
                NewsEvent.impact.in_(["HIGH", "MEDIUM"]),
                NewsEvent.time >= now,
                NewsEvent.time <= window_end,
                NewsEvent.telegram_sent == False,
            ).order_by(NewsEvent.time)
        )
        events = result.scalars().all()

    if not events:
        return []

    alerts = []
    for event in events:
        if event.news_id in _alerted_news_ids:
            continue
        _alerted_news_ids.add(event.news_id)

        msg = _format_event_alert(event)
        try:
            await _broadcast_to_all_users(msg)
            async with async_session_factory() as session:
                ev = (
                    await session.execute(select(NewsEvent).where(NewsEvent.news_id == event.news_id))
                ).scalar_one_or_none()
                if ev:
                    ev.telegram_sent = True
                    await session.commit()
            alerts.append({"news_id": event.news_id, "event": event.event, "sent": True})
            logger.info("Alert sent for event: %s (%s)", event.event, event.currency)
        except Exception as e:
            logger.error("Failed to send alert for %s: %s", event.news_id, e)
            alerts.append({"news_id": event.news_id, "event": event.event, "sent": False, "error": str(e)})

    return alerts


async def send_weekly_calendar():
    """Send the weekly economic calendar on Sundays."""
    now = datetime.now(timezone.utc)
    weekday = now.weekday()
    week_start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=weekday)
    week_end = week_start + timedelta(days=7)

    async with async_session_factory() as session:
        result = await session.execute(
            select(NewsEvent).where(
                NewsEvent.time >= week_start,
                NewsEvent.time <= week_end,
                NewsEvent.impact.in_(["HIGH", "MEDIUM"]),
            ).order_by(NewsEvent.time).limit(50)
        )
        events = result.scalars().all()

    if not events:
        logger.info("No events for weekly calendar")
        return 0

    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    lines = ["📅 <b>Weekly Economic Calendar</b>\n"]
    current_day = -1

    for ev in events:
        if not ev.time:
            continue
        ev_day = ev.time.weekday()
        if ev_day != current_day:
            current_day = ev_day
            lines.append(f"\n<b>{day_names[ev_day]}</b>")

        t = ev.time.strftime("%H:%M") if ev.time else "—"
        impact_icon = "🔴" if ev.impact == "HIGH" else "🟠"
        parts = [f"  {impact_icon} {t} | {ev.currency} | {ev.event}"]
        if ev.forecast:
            parts.append(f"Fcst:{ev.forecast}")
        if ev.previous:
            parts.append(f"Prev:{ev.previous}")
        lines.append(" | ".join(parts))

    msg = "\n".join(lines)

    if len(msg) > 4000:
        msg = msg[:3997] + "..."

    count = await _broadcast_to_all_users(msg)
    logger.info("Weekly calendar sent to %d users", count)
    return count


def _format_event_alert(event: NewsEvent) -> str:
    t = event.time.strftime("%H:%M UTC") if event.time else "—"
    impact_icon = "🔴 HIGH" if event.impact == "HIGH" else "🟠 MEDIUM"
    lines = [
        f"⚠️ <b>Upcoming Economic Event</b>\n",
        f"{impact_icon} <b>{event.event}</b>",
        f"🕐 {t}",
        f"💱 {event.currency}",
    ]
    if event.forecast:
        lines.append(f"📊 Forecast: {event.forecast}")
    if event.previous:
        lines.append(f"📈 Previous: {event.previous}")
    lines.append(f"\n⏳ Trading will be blocked 30min before this event.")
    return "\n".join(lines)


async def _broadcast_to_all_users(message: str) -> int:
    """Send a message to all users with a telegram_id."""
    from database.models import User

    TELEGRAM_BOT_TOKEN = __import__("os").getenv("TELEGRAM_BOT_TOKEN")
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not set, skipping broadcast")
        return 0

    from telegram import Bot
    from telegram.constants import ParseMode

    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    count = 0

    async with async_session_factory() as session:
        result = await session.execute(
            select(User).where(User.telegram_id.isnot(None))
        )
        users = result.scalars().all()

        for user in users:
            try:
                await bot.send_message(
                    chat_id=int(user.telegram_id),
                    text=message,
                    parse_mode=ParseMode.HTML,
                )
                count += 1
            except Exception as e:
                logger.warning("Failed to send to telegram_id %s: %s", user.telegram_id, e)

    logger.info("Broadcast sent to %d/%d users", count, len(users))
    return count


def _parse_dt(val):
    if val is None or (isinstance(val, str) and val.strip() in ("", "None", "nan", "NaT")):
        return None
    import pandas as pd
    try:
        dt = pd.to_datetime(val, errors="coerce")
        if pd.isna(dt):
            return None
        return dt.to_pydatetime().replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.to_pydatetime()
    except Exception:
        return None


def _str_or_none(val):
    if val is None or (isinstance(val, str) and val.strip().lower() in ("", "nan", "none", "nat")):
        return None
    return str(val).strip()[:100]


def _safe_int(val, default=1):
    try:
        if val is None:
            return default
        return int(float(str(val)))
    except Exception:
        return default


def _safe_bool(val):
    if val is None:
        return False
    if isinstance(val, bool):
        return val
    v = str(val).strip().lower()
    return v in ("true", "1", "yes")

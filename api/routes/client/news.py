"""Client economic calendar (Sprint — news integration).

Single canonical source: DB `news_events` (populated by the news engine via
the CSV bridge in api/services/news_broadcast.sync_csv_to_db).

Endpoints:
  GET /api/client/news            upcoming high/medium events (next 7 days)
  GET /api/client/news/recent     recently released events with actuals
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import get_session
from database.models import NewsEvent
from security.auth import get_current_user

router = APIRouter(prefix="/client/news", tags=["client-news"])

_NOW = None  # injectable for tests


def _now() -> datetime:
    if _NOW is not None:
        return _NOW
    return datetime.now(timezone.utc)


def _event_payload(ev: NewsEvent) -> dict:
    return {
        "news_id": ev.news_id,
        "time": ev.time.isoformat() if ev.time else None,
        "currency": ev.currency,
        "event": ev.event,
        "impact": ev.impact,
        "actual": ev.actual,
        "forecast": ev.forecast,
        "previous": ev.previous,
        "status": ev.status,
    }


@router.get("")
async def client_news_calendar(
    days: int = Query(7, ge=1, le=30),
    impact: str = Query("HIGH,MEDIUM", description="comma-separated HIGH/MEDIUM/LOW"),
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Upcoming high/medium impact events from now through `days` days ahead."""
    now = _now()
    horizon = now + timedelta(days=days)
    impacts = [i.strip().upper() for i in impact.split(",") if i.strip()]

    query = select(NewsEvent).where(
        NewsEvent.time >= now,
        NewsEvent.time <= horizon,
    )
    if impacts:
        query = query.where(NewsEvent.impact.in_(impacts))
    query = query.order_by(NewsEvent.time).limit(200)

    rows = (await session.execute(query)).scalars().all()

    return {
        "items": [_event_payload(ev) for ev in rows],
        "total": len(rows),
        "window_days": days,
    }


@router.get("/recent")
async def client_news_recent(
    hours: int = Query(48, ge=1, le=168),
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Released events (have an actual value) from the last `hours` hours."""
    now = _now()
    start = now - timedelta(hours=hours)

    rows = (
        (
            await session.execute(
                select(NewsEvent)
                .where(
                    NewsEvent.time >= start,
                    NewsEvent.time <= now,
                    NewsEvent.actual.isnot(None),
                )
                .order_by(NewsEvent.time.desc())
                .limit(100)
            )
        )
        .scalars()
        .all()
    )

    return {
        "items": [_event_payload(ev) for ev in rows],
        "total": len(rows),
        "window_hours": hours,
    }

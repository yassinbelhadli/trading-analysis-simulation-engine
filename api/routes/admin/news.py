from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import get_session
from database.models import News
from security.auth import Permission, log_event, require_permission

router = APIRouter(tags=["admin", "news"])


# ---------------------------------------------------------------------------
# Economic Calendar Engine Status
# ---------------------------------------------------------------------------
@router.get("/news/engine-status")
async def news_engine_status(
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission(Permission.ADMIN_OVERVIEW)),
):
    """Engine status from the canonical source: DB `news_events`.

    Previously this read the CSV cache (frozen on 2026-07-23) and compared
    naive datetimes against aware `now` — stale numbers and a TypeError.
    All dashboards and alerts now read the same DB table.
    """
    from database.models import NewsEvent

    now = datetime.now(timezone.utc)

    result = {
        "running": False,
        "last_fetch": None,
        "last_fetch_ago_sec": None,
        "total_events": 0,
        "upcoming_high": [],
        "usd_events_today": 0,
        "cache_exists": False,
        "db_events": 0,
    }

    # DB event count
    db_count = await session.execute(select(func.count()).select_from(NewsEvent))
    result["db_events"] = db_count.scalar() or 0
    result["total_events"] = result["db_events"]

    # Last fetch = most recent row creation/update in the DB
    last_row = (
        await session.execute(
            select(NewsEvent.last_checked, NewsEvent.updated_at, NewsEvent.first_seen)
            .where(NewsEvent.last_checked.isnot(None))
            .order_by(NewsEvent.last_checked.desc())
            .limit(1)
        )
    ).first()
    last_fetch_dt = None
    if last_row:
        last_fetch_dt = last_row[0] or last_row[1] or last_row[2]
    if last_fetch_dt:
        if last_fetch_dt.tzinfo is None:
            last_fetch_dt = last_fetch_dt.replace(tzinfo=timezone.utc)
        result["last_fetch"] = last_fetch_dt.isoformat()
        result["last_fetch_ago_sec"] = int((now - last_fetch_dt).total_seconds())

    # Upcoming high/medium events from DB
    upcoming = (
        await session.execute(
            select(NewsEvent)
            .where(
                NewsEvent.time >= now,
                NewsEvent.impact.in_(["HIGH", "MEDIUM"]),
            )
            .order_by(NewsEvent.time)
            .limit(20)
        )
    ).scalars().all()
    for ev in upcoming:
        result["upcoming_high"].append({
            "news_id": ev.news_id,
            "time": ev.time.isoformat() if ev.time else None,
            "currency": ev.currency,
            "event": ev.event,
            "impact": ev.impact,
            "forecast": ev.forecast,
            "previous": ev.previous,
        })

    # USD events today from DB
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start.replace(hour=23, minute=59, second=59, microsecond=999999)
    usd_today = (
        await session.execute(
            select(func.count())
            .select_from(NewsEvent)
            .where(
                NewsEvent.time >= today_start,
                NewsEvent.time <= today_end,
                NewsEvent.currency == "USD",
            )
        )
    ).scalar() or 0
    result["usd_events_today"] = usd_today
    result["running"] = result["db_events"] > 0

    return result


@router.get("/news")
async def list_news(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    published: bool = None,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission(Permission.ADMIN_OVERVIEW)),
):
    query = select(News).order_by(News.created_at.desc())
    count_query = select(func.count()).select_from(News)
    if published is not None:
        query = query.where(News.published == published)
        count_query = count_query.where(News.published == published)
    total = (await session.execute(count_query)).scalar() or 0
    query = query.offset(offset).limit(limit)
    result = await session.execute(query)
    items = result.scalars().all()
    return {
        "items": [
            {
                "id": n.id,
                "title": n.title,
                "body": n.body,
                "category": n.category,
                "published": n.published,
                "telegram_sent": n.telegram_sent,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in items
        ],
        "total": total,
    }


@router.post("/news")
async def create_news(
    body: dict,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission(Permission.ADMIN_OVERVIEW)),
):
    title = (body.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Title required")
    news = News(
        title=title,
        body=body.get("body", ""),
        category=body.get("category", "general"),
        published=body.get("published", False),
        telegram_sent=False,
    )
    session.add(news)
    await session.flush()
    audit_id = await log_event(session, "news.created", f"News '{title}' created",
                                user_id=current_user.id, payload={"news_id": news.id})
    await session.commit()
    return {"id": news.id, "audit_id": audit_id, "message": "News created"}


@router.patch("/news/{news_id}")
async def update_news(
    news_id: str,
    body: dict,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission(Permission.ADMIN_OVERVIEW)),
):
    result = await session.execute(select(News).where(News.id == news_id))
    n = result.scalar_one_or_none()
    if not n:
        raise HTTPException(status_code=404, detail="News not found")
    if "title" in body:
        n.title = body["title"]
    if "body" in body:
        n.body = body["body"]
    if "category" in body:
        n.category = body["category"]
    if "published" in body:
        n.published = body["published"]
    audit_id = await log_event(session, "news.updated", f"News '{n.title}' updated",
                                user_id=current_user.id)
    await session.commit()
    return {"success": True, "audit_id": audit_id, "message": "News updated"}


@router.delete("/news/{news_id}")
async def delete_news(
    news_id: str,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission(Permission.ADMIN_OVERVIEW)),
):
    result = await session.execute(select(News).where(News.id == news_id))
    n = result.scalar_one_or_none()
    if not n:
        raise HTTPException(status_code=404, detail="News not found")
    await session.delete(n)
    audit_id = await log_event(session, "news.deleted", f"News '{n.title}' deleted",
                                user_id=current_user.id)
    await session.commit()
    return {"success": True, "audit_id": audit_id, "message": "News deleted"}


@router.post("/news/{news_id}/broadcast")
async def broadcast_news(
    news_id: str,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission(Permission.ADMIN_OVERVIEW)),
):
    result = await session.execute(select(News).where(News.id == news_id))
    n = result.scalar_one_or_none()
    if not n:
        raise HTTPException(status_code=404, detail="News not found")
    broadcasted = 0
    try:
        from services.telegram_service import broadcast_message
        broadcasted = await broadcast_message(f"📢 {n.title}\n\n{n.body}")
        n.telegram_sent = True
    except ImportError:
        pass
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Broadcast failed: {e}")
    audit_id = await log_event(session, "news.broadcast", f"News '{n.title}' broadcast to {broadcasted} users",
                                user_id=current_user.id, payload={"broadcasted": broadcasted})
    await session.commit()
    return {"success": True, "audit_id": audit_id, "broadcasted": broadcasted, "message": "News broadcast"}

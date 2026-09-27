from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import get_session
from database.models import AuditLog, User
from security.auth import Permission, require_permission

router = APIRouter(tags=["admin", "audit"])


@router.get("/audit-logs")
async def list_audit_logs(
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
    actor: str = None,
    action: str = None,
    severity: str = None,
    date_from: str = None,
    date_to: str = None,
    q: str = None,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission(Permission.AUDIT_READ)),
):
    query = select(AuditLog)
    count_query = select(func.count()).select_from(AuditLog)

    if actor:
        query = query.where(AuditLog.user_id == actor)
        count_query = count_query.where(AuditLog.user_id == actor)
    if action:
        query = query.where(AuditLog.event_type.ilike(f"%{action}%"))
        count_query = count_query.where(AuditLog.event_type.ilike(f"%{action}%"))
    if q:
        # Free-text search across the fields the Owner UI labels as searchable:
        # actor, action/event type, target/account. ILIKE OR over indexed columns
        # only — the audit log is append-only, so this stays cheap at LIMIT size.
        like = f"%{q}%"
        query = query.where(
            AuditLog.event_type.ilike(like)
            | AuditLog.user_id.ilike(like)
            | AuditLog.account_id.ilike(like)
        )
        count_query = count_query.where(
            AuditLog.event_type.ilike(like)
            | AuditLog.user_id.ilike(like)
            | AuditLog.account_id.ilike(like)
        )

    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(query)
    logs = result.scalars().all()

    return {
        "items": [
            {
                "id": log.id,
                "timestamp": log.created_at.isoformat() if log.created_at else None,
                "actor": log.user_id,
                "action": log.event_type,
                "severity": log.severity,
                "resource": log.source,
                "target": log.account_id,
                "result": log.severity,
                "ip": (log.payload_json or {}).get("ip"),
                "details": log.payload_json,
            }
            for log in logs
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/audit-logs/summary")
async def audit_log_summary(
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission(Permission.AUDIT_READ)),
):
    result = await session.execute(
        select(AuditLog.severity, func.count().label("count"))
        .group_by(AuditLog.severity)
    )
    by_severity = {row.severity: row.count for row in result.all()}

    result = await session.execute(
        select(AuditLog.event_type, func.count().label("count"))
        .group_by(AuditLog.event_type)
        .order_by(func.count().desc())
        .limit(10)
    )
    top_actions = [{"action": row.event_type, "count": row.count} for row in result.all()]

    total = await session.execute(select(func.count()).select_from(AuditLog))
    total_count = total.scalar() or 0

    return {"total": total_count, "by_severity": by_severity, "top_actions": top_actions}

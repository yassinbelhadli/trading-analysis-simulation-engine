from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from database.db import async_session_factory
from database.repositories.audit_repository import AuditRepository

admin_audit_router = APIRouter()


@admin_audit_router.get("/audit/recent")
async def get_recent_audit_logs(
    limit: int = Query(100, le=500),
    severity: Optional[str] = None,
    source: Optional[str] = None,
):
    async with async_session_factory() as session:
        repo = AuditRepository(session)
        logs = await repo.get_recent(limit=limit, severity=severity)
        if source:
            logs = [l for l in logs if l.source == source]
        return [
            {
                "id": log.id,
                "event_type": log.event_type,
                "severity": log.severity,
                "source": log.source,
                "message": log.message[:500],
                "account_id": log.account_id,
                "user_id": log.user_id,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ]


@admin_audit_router.get("/audit/by-account/{account_id}")
async def get_audit_by_account(
    account_id: str,
    limit: int = Query(100, le=500),
):
    async with async_session_factory() as session:
        repo = AuditRepository(session)
        logs = await repo.get_by_account(account_id, limit=limit)
        return [
            {
                "id": log.id,
                "event_type": log.event_type,
                "severity": log.severity,
                "source": log.source,
                "message": log.message[:500],
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ]


@admin_audit_router.get("/audit/by-severity")
async def get_audit_severity_counts():
    async with async_session_factory() as session:
        repo = AuditRepository(session)
        counts = await repo.count_by_severity()
        return counts

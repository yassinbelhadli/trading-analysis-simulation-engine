from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from database.models import AuditLog

logger = logging.getLogger(__name__)


async def log_event(
    session: AsyncSession,
    event_type: str,
    message: str,
    user_id: Optional[str] = None,
    account_id: Optional[str] = None,
    severity: str = "INFO",
    source: str = "web",
    payload: Optional[dict] = None,
    commit: bool = False,
) -> str:
    """Write an audit log entry and return its ID.

    By default the entry is only flushed (no commit) so the caller can
    commit it atomically with the main operation.  Pass ``commit=True``
    when no other commit follows.
    """
    entry = AuditLog(
        user_id=user_id,
        account_id=account_id,
        event_type=event_type,
        severity=severity,
        source=source,
        message=message,
        payload_json=payload or {},
    )
    session.add(entry)
    await session.flush()
    if commit:
        await session.commit()
    logger.info("[audit] %s | %s | id=%s", event_type, message, entry.id)
    return entry.id

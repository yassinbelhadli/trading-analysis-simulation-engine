"""Phase 6.0 — permission-gated delivery endpoints (emails.* / telegram.send).

These turn the previously unused `emails.read`, `emails.send` and
`telegram.send` permissions into real, audited API surface. All provider calls
honour the existing mock/test-mode environment gates (TELEGRAM_TEST_MODE,
EMAIL_TEST_MODE) so QA/CI never touches real providers.
"""
from __future__ import annotations

import os
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import BOT_USERNAME, SMTP_PASS, SMTP_USER, TELEGRAM_BOT_TOKEN
from database.db import get_session
from database.models import AuditLog, User
from security.auth import Permission, log_event, require_permission

router = APIRouter(tags=["admin", "notifications"])

_DELIVERY_EVENTS = ("email.test", "telegram.test", "notification.delivery")


def _config_status() -> Dict[str, bool]:
    return {
        "email_configured": bool(SMTP_USER and SMTP_PASS),
        "telegram_configured": bool(TELEGRAM_BOT_TOKEN),
        "telegram_test_mode": os.getenv("TELEGRAM_TEST_MODE", "").lower() == "true",
        "email_test_mode": os.getenv("EMAIL_TEST_MODE", "").lower() == "true",
    }


async def _recent_deliveries(session: AsyncSession, limit: int = 20) -> list:
    result = await session.execute(
        select(AuditLog)
        .where(AuditLog.event_type.in_(_DELIVERY_EVENTS))
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    rows = []
    for row in result.scalars().all():
        rows.append({
            "id": row.id,
            "event_type": row.event_type,
            "message": row.message,
            "user_id": row.user_id,
            "severity": row.severity,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        })
    return rows


# ---------------------------------------------------------------------------
# emails.read
# ---------------------------------------------------------------------------
@router.get("/emails/status")
async def emails_status(
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission(Permission.EMAIL_READ)),
):
    """Email channel status + recent delivery records. Never returns secrets."""
    return {
        **_config_status(),
        "recent_deliveries": await _recent_deliveries(session),
    }


# ---------------------------------------------------------------------------
# emails.send
# ---------------------------------------------------------------------------
@router.post("/emails/test")
async def emails_test(
    body: dict,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission(Permission.EMAIL_SEND)),
):
    """Send a test email (mock in EMAIL_TEST_MODE; audited)."""
    to = (body.get("to") or "").strip() or SMTP_USER or "test@ictfundedeapro.com"
    mock = _config_status()["email_test_mode"]
    if mock:
        ok, detail = True, "mocked"
    else:
        try:
            from api.services.email_service import send_email
            ok = await send_email(to, "Test Email — ICT EA Pro",
                                  "This is a test email from the admin console.",
                                  session=session)
            detail = "sent" if ok else "smtp delivery failed"
        except Exception as e:
            ok, detail = False, str(e)
    audit_id = await log_event(session, "email.test",
                               f"Test email to {to} — {'mocked' if mock else ('sent' if ok else 'failed')}",
                               user_id=current_user.id, payload={"to": to, "ok": ok, "mock": mock})
    await session.commit()
    return {"success": ok, "mock": mock, "message": detail, "audit_id": audit_id}


# ---------------------------------------------------------------------------
# telegram.send
# ---------------------------------------------------------------------------
@router.get("/telegram/status")
async def telegram_status(
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission(Permission.TELEGRAM_SEND)),
):
    """Telegram channel status + linked user count + recent delivery records."""
    count = 0
    try:
        result = await session.execute(
            select(func.count()).select_from(User).where(User.telegram_id.isnot(None))
        )
        count = result.scalar() or 0
    except Exception:
        pass
    return {
        **_config_status(),
        "bot_username": BOT_USERNAME,
        "linked_users": count,
        "recent_deliveries": await _recent_deliveries(session),
    }


@router.post("/telegram/test")
async def telegram_test(
    body: dict,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_permission(Permission.TELEGRAM_SEND)),
):
    """Send a test Telegram message (mock in TELEGRAM_TEST_MODE; audited)."""
    chat_id = body.get("chat_id")
    try:
        chat_id = int(chat_id) if chat_id else None
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="chat_id must be an integer")

    if not TELEGRAM_BOT_TOKEN and not _config_status()["telegram_test_mode"]:
        raise HTTPException(status_code=400, detail="Telegram bot is not configured")

    from api.services.notifications.channels import TelegramChannel

    text = "✅ Test notification from ICT Funded EA Pro."
    res = await TelegramChannel().deliver(chat_id=chat_id, text=text)
    audit_id = await log_event(session, "telegram.test",
                               f"Test telegram message — {res.status}",
                               user_id=current_user.id,
                               payload={"chat_id": chat_id, "status": res.status})
    await session.commit()
    return {"success": res.ok, "mock": res.status == "delivered" and "mocked" == res.detail,
            "message": res.detail or res.status, "audit_id": audit_id}

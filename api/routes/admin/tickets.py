"""Admin / staff support-tickets API.

Upgraded workspace over the shared ``support_tickets`` + ``ticket_messages``
records (the same records the Client Dashboard, Telegram bot and Owner Portal
read and write):

- filterable listing (status / priority / category / escalated / assignee / search)
- full conversation view including internal staff notes (staff-only)
- public replies + internal notes
- validated status/priority/category updates with closed/resolved semantics
- assignment (``tickets.assign``)
- escalation with full metadata (who / when / target / reason)
- ban (``tickets.ban`` — owner-only in the permission map)

Every mutation is audited and committed atomically inside the service layer;
responses use the unified ``{success, audit_id, message}`` contract.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.rate_limit import rate_limit
from api.services.ticket_service import (
    TICKET_CATEGORIES,
    TICKET_PRIORITIES,
    TICKET_STATUSES,
    add_message,
    ban_ticket_user,
    escalate_ticket,
    get_ticket_or_none,
    list_tickets_admin,
    serialize_ticket_admin,
    update_ticket_fields,
)
from database.db import get_session
from database.models import User
from security.auth import Permission, get_current_user, require_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tickets", tags=["tickets"])


def _staff_role(user: User) -> str:
    return user.role_rel.name if user.role_rel else "support"


def _author_name(user: User) -> str:
    return f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email or None


# ---------------------------------------------------------------------------
# GET /api/tickets  (filterable listing)
# ---------------------------------------------------------------------------
@router.get("")
async def list_tickets(
    status: str = Query(None),
    priority: str = Query(None),
    category: str = Query(None),
    escalated: bool = Query(None),
    assignee_id: str = Query(None),
    search: str = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission(Permission.TICKETS_READ)),
):
    for name, value, allowed in (
        ("status", status, TICKET_STATUSES),
        ("priority", priority, TICKET_PRIORITIES),
        ("category", category, TICKET_CATEGORIES),
    ):
        if value and value not in allowed:
            raise HTTPException(400, f"Invalid {name}. Use one of: {', '.join(sorted(allowed))}")

    tickets, total = await list_tickets_admin(
        session,
        status=status, priority=priority, category=category,
        escalated=escalated, assignee_id=assignee_id, search=search,
        page=page, limit=limit,
    )
    return {"success": True, "tickets": tickets, "total": total, "page": page, "limit": limit}


# ---------------------------------------------------------------------------
# GET /api/tickets/metrics  (workload metrics — owner portal)
# Registered before /{ticket_id} so "metrics" is never captured as an id.
# ---------------------------------------------------------------------------
@router.get("/metrics")
async def ticket_metrics_endpoint(
    assignee_id: str = Query(None),
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission(Permission.TICKETS_READ)),
):
    from api.services.ticket_service import ticket_metrics

    return {"success": True, "metrics": await ticket_metrics(session, assignee_id=assignee_id)}


# ---------------------------------------------------------------------------
# GET /api/tickets/{ticket_id}  (full view incl. internal notes)
# ---------------------------------------------------------------------------
@router.get("/{ticket_id}")
async def get_ticket(
    ticket_id: str,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission(Permission.TICKETS_READ)),
):
    ticket = await get_ticket_or_none(session, ticket_id)
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    return {"success": True, "ticket": await serialize_ticket_admin(session, ticket)}


# ---------------------------------------------------------------------------
# POST /api/tickets/{ticket_id}/reply   (public reply or internal note)
# ---------------------------------------------------------------------------
@router.post("/{ticket_id}/reply", dependencies=[Depends(rate_limit(20, 60))])
async def reply_to_ticket(
    ticket_id: str,
    body: dict,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _=Depends(require_permission(Permission.TICKETS_UPDATE)),
):
    ticket = await get_ticket_or_none(session, ticket_id)
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    if ticket.status == "closed":
        raise HTTPException(400, "Ticket is closed. Reopen it before replying.")

    message = str(body.get("message", "")).strip()
    if not 1 <= len(message) <= 5000:
        raise HTTPException(400, "Message must be between 1 and 5000 characters")
    is_internal = bool(body.get("is_internal", False))

    _, audit_id = await add_message(
        session,
        ticket,
        body=message,
        author_user_id=current_user.id,
        author_role=_staff_role(current_user),
        author_name=_author_name(current_user),
        is_internal=is_internal,
        notify=True,
    )
    return {
        "success": True,
        "audit_id": audit_id,
        "message": "Internal note added" if is_internal else "Reply added",
    }


# ---------------------------------------------------------------------------
# PATCH /api/tickets/{ticket_id}   (validated status/priority/category)
# ---------------------------------------------------------------------------
@router.patch("/{ticket_id}")
async def update_ticket(
    ticket_id: str,
    body: dict,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _=Depends(require_permission(Permission.TICKETS_UPDATE)),
):
    ticket = await get_ticket_or_none(session, ticket_id)
    if not ticket:
        raise HTTPException(404, "Ticket not found")

    allowed = {"status", "priority", "category"}
    fields = {k: v for k, v in body.items() if k in allowed and v is not None}
    if not fields:
        raise HTTPException(400, "No valid fields to update")

    try:
        changes, audit_id = await update_ticket_fields(
            session, ticket, fields=fields, actor=current_user, actor_role=_staff_role(current_user)
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    if not changes:
        return {"success": True, "message": "No changes", "changes": {}}

    # Notify the client of status changes (best-effort).
    if "status" in changes:
        await _notify_status_change(ticket, changes["status"])
    return {"success": True, "audit_id": audit_id, "message": "Ticket updated", "changes": changes}


# ---------------------------------------------------------------------------
# POST /api/tickets/{ticket_id}/assign   (tickets.assign)
# ---------------------------------------------------------------------------
@router.post("/{ticket_id}/assign")
async def assign_ticket(
    ticket_id: str,
    body: dict,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _=Depends(require_permission(Permission.TICKETS_ASSIGN)),
):
    ticket = await get_ticket_or_none(session, ticket_id)
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    raw = body.get("assignee_id")
    if raw is None:
        raise HTTPException(400, "assignee_id is required")
    assignee_id = str(raw).strip()
    # "none" / empty are the explicit unassign tokens sent by the admin dashboard
    if assignee_id.lower() in ("none", ""):
        assignee_id = ""

    try:
        changes, audit_id = await update_ticket_fields(
            session, ticket, fields={"assignee_id": assignee_id},
            actor=current_user, actor_role=_staff_role(current_user),
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    if not changes:
        return {"success": True, "message": "Assignee unchanged"}

    assignee = None
    if ticket.assignee_id:
        result = await session.execute(select(User).where(User.id == ticket.assignee_id))
        a = result.scalar_one_or_none()
        if a:
            assignee = {
                "id": a.id, "first_name": a.first_name, "last_name": a.last_name,
                "email": a.email, "role": a.role_rel.name if a.role_rel else None,
            }
    return {
        "success": True,
        "audit_id": audit_id,
        "message": "Ticket assigned",
        "assignee": assignee,
    }


# ---------------------------------------------------------------------------
# POST /api/tickets/{ticket_id}/escalate   (full metadata, tickets.update)
# ---------------------------------------------------------------------------
@router.post("/{ticket_id}/escalate")
async def escalate_ticket_route(
    ticket_id: str,
    body: dict,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _=Depends(require_permission(Permission.TICKETS_UPDATE)),
):
    ticket = await get_ticket_or_none(session, ticket_id)
    if not ticket:
        raise HTTPException(404, "Ticket not found")

    target = str(body.get("target", "admin")).strip().lower()
    reason = str(body.get("reason", "")).strip() or "No reason provided"
    try:
        audit_id = await escalate_ticket(
            session, ticket, actor=current_user, target=target, reason=reason
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {
        "success": True,
        "audit_id": audit_id,
        "message": f"Ticket escalated to {target}",
        "escalated_at": ticket.escalated_at.isoformat() if ticket.escalated_at else None,
    }


# ---------------------------------------------------------------------------
# POST /api/tickets/{ticket_id}/ban   (tickets.ban — owner-only permission)
# ---------------------------------------------------------------------------
@router.post("/{ticket_id}/ban")
async def ban_ticket_user_route(
    ticket_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _=Depends(require_permission(Permission.TICKETS_BAN)),
):
    ticket = await get_ticket_or_none(session, ticket_id)
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    if not ticket.user:
        raise HTTPException(400, "User not found")

    audit_id = await ban_ticket_user(session, ticket, actor=current_user)
    return {
        "success": True,
        "audit_id": audit_id,
        "message": f"User {ticket.user_id} banned, licenses suspended",
    }


# ---------------------------------------------------------------------------
# Telegram status-change notification (best-effort, escaped)
# ---------------------------------------------------------------------------
async def _notify_status_change(ticket, status: str) -> None:
    if not (ticket.user and ticket.user.telegram_id):
        return
    try:
        from telegram_bot.api_client import telegram_application
        from api.services.ticket_service import _escape
        bot = telegram_application.app.bot
        lang = (ticket.user.language or "EN").upper()
        status_label = {
            "EN": {"open": "Open", "in_progress": "In Progress", "resolved": "Resolved", "closed": "Closed"},
            "AR": {"open": "مفتوحة", "in_progress": "قيد المعالجة", "resolved": "تم الحل", "closed": "مغلقة"},
            "FR": {"open": "Ouvert", "in_progress": "En cours", "resolved": "Résolu", "closed": "Fermé"},
            "ES": {"open": "Abierto", "in_progress": "En progreso", "resolved": "Resuelto", "closed": "Cerrado"},
        }.get(lang, {}).get(status, status)
        safe_num = _escape(ticket.ticket_number)
        safe_status = _escape(status_label)
        msg = {
            "EN": f"🔄 <b>Ticket {safe_num} status updated</b>\n\nNew status: <b>{safe_status}</b>",
            "AR": f"🔄 <b>تم تحديث حالة التذكرة {safe_num}</b>\n\nالحالة الجديدة: <b>{safe_status}</b>",
            "FR": f"🔄 <b>Ticket {safe_num} — statut mis à jour</b>\n\nNouveau statut: <b>{safe_status}</b>",
            "ES": f"🔄 <b>Ticket {safe_num} — estado actualizado</b>\n\nNuevo estado: <b>{safe_status}</b>",
        }
        await bot.send_message(chat_id=int(ticket.user.telegram_id), text=msg.get(lang, msg["EN"]), parse_mode="HTML")
    except Exception as e:
        logger.warning("Status-change Telegram push failed (ticket=%s): %s", ticket.ticket_number, e)

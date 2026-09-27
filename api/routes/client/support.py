"""Client support routes — the Client Dashboard's support center.

Contract notes:
- The client is always scoped to their OWN tickets: a foreign ticket_id is
  served as 404 (never 403) so ticket ids cannot be enumerated.
- Internal staff notes are filtered server-side; clients only ever receive
  public conversation messages.
- Ticket creation and replies are rate-limited with the shared rate limiter.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.rate_limit import rate_limit
from api.services.ticket_service import (
    TICKET_CATEGORIES,
    TICKET_PRIORITIES,
    TICKET_STATUSES,
    add_message,
    create_ticket,
    get_ticket_or_none,
    list_tickets_for_user,
    serialize_ticket,
)
from database.db import get_session
from database.models import User
from security.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/client/support", tags=["client", "support"])


def _client_payload(ticket) -> dict:
    payload = serialize_ticket(ticket, include_internal=False)
    # The client sees their own record; drop staff-only enrichment keys.
    payload.pop("user", None)
    payload.pop("license", None)
    payload.pop("assignee", None)
    payload.pop("assignee_id", None)
    payload.pop("replied_by", None)
    payload.pop("closed_by", None)
    payload.pop("escalated_by", None)
    payload.pop("escalation_target", None)
    return payload


# ---------------------------------------------------------------------------
# GET /api/client/support   (list own tickets)
# ---------------------------------------------------------------------------
@router.get("")
async def list_my_tickets(
    status: str = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if status and status not in TICKET_STATUSES:
        raise HTTPException(400, f"Invalid status. Use one of: {', '.join(sorted(TICKET_STATUSES))}")
    tickets, total = await list_tickets_for_user(
        session, current_user.id, status=status, page=page, limit=limit
    )
    return {
        "tickets": [_client_payload(t) for t in tickets],
        "total": total,
        "page": page,
        "limit": limit,
    }


# ---------------------------------------------------------------------------
# POST /api/client/support   (create ticket)
# ---------------------------------------------------------------------------
@router.post("", dependencies=[Depends(rate_limit(5, 60))])
async def create_my_ticket(
    body: dict,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    subject = str(body.get("subject", "")).strip()
    description = str(body.get("description", "")).strip()
    category = str(body.get("category", "other")).strip().lower()
    priority = str(body.get("priority", "medium")).strip().lower()

    if not 3 <= len(subject) <= 255:
        raise HTTPException(400, "Subject must be between 3 and 255 characters")
    if not 10 <= len(description) <= 5000:
        raise HTTPException(400, "Description must be between 10 and 5000 characters")
    if category not in TICKET_CATEGORIES:
        raise HTTPException(400, f"Invalid category. Use one of: {', '.join(sorted(TICKET_CATEGORIES))}")
    if priority not in TICKET_PRIORITIES:
        raise HTTPException(400, f"Invalid priority. Use one of: {', '.join(sorted(TICKET_PRIORITIES))}")

    ticket = await create_ticket(
        session,
        user=current_user,
        subject=subject,
        description=description,
        category=category,
        priority=priority,
        source="dashboard",
    )
    return {"ticket": _client_payload(ticket), "message": "Ticket created"}


# ---------------------------------------------------------------------------
# GET /api/client/support/{ticket_id}   (read own ticket + conversation)
# ---------------------------------------------------------------------------
@router.get("/{ticket_id}")
async def get_my_ticket(
    ticket_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    ticket = await get_ticket_or_none(session, ticket_id)
    if not ticket or ticket.user_id != current_user.id:
        raise HTTPException(404, "Ticket not found")
    return {"ticket": _client_payload(ticket)}


# ---------------------------------------------------------------------------
# POST /api/client/support/{ticket_id}/reply
# ---------------------------------------------------------------------------
@router.post("/{ticket_id}/reply", dependencies=[Depends(rate_limit(10, 60))])
async def reply_my_ticket(
    ticket_id: str,
    body: dict,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    ticket = await get_ticket_or_none(session, ticket_id)
    if not ticket or ticket.user_id != current_user.id:
        raise HTTPException(404, "Ticket not found")
    if ticket.status == "closed":
        raise HTTPException(400, "This ticket is closed. Please open a new ticket.")

    message = str(body.get("message", "")).strip()
    if not 1 <= len(message) <= 5000:
        raise HTTPException(400, "Message must be between 1 and 5000 characters")

    await add_message(
        session,
        ticket,
        body=message,
        author_user_id=current_user.id,
        author_role="client",
        author_name=f"{current_user.first_name or ''} {current_user.last_name or ''}".strip() or None,
        is_internal=False,
        notify=False,  # client messages go straight into the ticket; no push
    )
    return {"message": "Reply added", "ticket": _client_payload(ticket)}

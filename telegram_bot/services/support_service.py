"""Telegram-facing support/ticket facade.

Thin adapter over the shared ``api.services.ticket_service`` so the Telegram
bot writes to the SAME ``support_tickets`` / ``ticket_messages`` records used
by the Client Dashboard, Admin Dashboard and Owner Portal.

No business logic lives here — all creation, validation, numbering, audit and
notification behaviour is delegated to the shared service layer.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.ticket_service import (
    add_message,
    create_ticket,
    get_ticket_or_none,
    serialize_ticket,
)
from database.models import SupportTicket, User

logger = logging.getLogger(__name__)

MAX_TELEGRAM_TICKETS = 10


async def create_ticket_for_telegram(
    session: AsyncSession,
    user: User,
    category: str,
    description: str,
    *,
    client_ref: str = "",
) -> SupportTicket:
    """Create a ticket from the Telegram bot (shared records, race-free number)."""
    return await create_ticket(
        session,
        user=user,
        subject=category,
        description=description,
        category=category,
        priority="medium",
        source="telegram",
        notify=True,
    )


async def list_my_tickets(
    session: AsyncSession,
    user_id: str,
    *,
    status: Optional[str] = None,
    limit: int = MAX_TELEGRAM_TICKETS,
):
    """Most recent tickets for the user (public view)."""
    query = (
        select(SupportTicket)
        .where(SupportTicket.user_id == user_id)
        .order_by(SupportTicket.created_at.desc())
        .limit(limit)
    )
    if status:
        query = query.where(SupportTicket.status == status)
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_my_ticket(
    session: AsyncSession,
    user_id: str,
    ticket_id: str,
) -> Optional[SupportTicket]:
    """Ticket if it belongs to the user (ownership enforced), else None."""
    ticket = await get_ticket_or_none(session, ticket_id)
    if not ticket or ticket.user_id != user_id:
        return None
    return ticket


async def reply_to_my_ticket(
    session: AsyncSession,
    ticket: SupportTicket,
    user: User,
    text: str,
) -> str:
    """Append a client message to the shared conversation; returns audit id."""
    _, audit_id = await add_message(
        session,
        ticket,
        body=text,
        author_user_id=user.id,
        author_role="client",
        author_name=f"{user.first_name or ''} {user.last_name or ''}".strip() or None,
        is_internal=False,
        notify=False,  # client messages are read in the staff workspaces
    )
    return audit_id


def public_payload(ticket: SupportTicket) -> dict:
    """Client-safe ticket payload (internal staff notes filtered server-side)."""
    payload = serialize_ticket(ticket, include_internal=False)
    payload.pop("user", None)
    payload.pop("assignee_id", None)
    payload.pop("replied_by", None)
    payload.pop("closed_by", None)
    payload.pop("escalated_by", None)
    payload.pop("escalation_target", None)
    return payload

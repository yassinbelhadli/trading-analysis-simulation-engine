"""Unified support/ticket service layer.

Single source of truth for the ticket lifecycle shared by the Client
Dashboard, Telegram bot, Admin Dashboard and Owner Portal.

Contract:
- Every mutation is audited (``security.audit.log_event``) and committed in the
  same transaction as the operation itself.
- Internal staff notes (``TicketMessage.is_internal = True``) are never
  returned to client-visible surfaces — filtering happens server-side.
- Ticket numbers are allocated from the ``support_ticket_seq`` Postgres
  sequence so concurrent creations can never collide (the legacy COUNT+1
  numbering raced under concurrency). The sequence is created idempotently
  as a safety net for ``create_all``-managed environments (QA).
- Notifications (email / Telegram) are best-effort: failures are logged and
  never fail the ticket operation.
- All user-supplied content embedded into Telegram HTML messages is escaped
  with ``html.escape`` before being sent.
"""
from __future__ import annotations

import html
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import License, SupportTicket, TicketMessage, User
from security.audit import log_event

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Validation enums (shared by every surface)
# ---------------------------------------------------------------------------
TICKET_CATEGORIES = {"connection", "license", "performance", "billing", "account", "bug", "other"}
TICKET_STATUSES = {"open", "in_progress", "resolved", "closed"}
TICKET_PRIORITIES = {"low", "medium", "high", "urgent"}
ESCALATION_TARGETS = {"developer", "admin", "owner"}

# Message author roles (mirrors staff roles; "system" for automated entries)
AUTHOR_ROLES = {"client", "support", "developer", "admin", "owner", "system"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _escape(value) -> str:
    """HTML-escape dynamic content destined for Telegram ``parse_mode=HTML``."""
    return html.escape(str(value or ""), quote=False)


# ---------------------------------------------------------------------------
# Ticket numbering  (concurrency-safe)
# ---------------------------------------------------------------------------
async def allocate_ticket_number(session: AsyncSession) -> str:
    """Return the next ``TKT-XXXX`` number using the Postgres sequence.

    The sequence is created if missing so environments that build schema with
    ``create_all`` (QA) keep the same race-free behaviour as migrated ones.
    """
    await session.execute(text("CREATE SEQUENCE IF NOT EXISTS support_ticket_seq"))
    result = await session.execute(text("SELECT nextval('support_ticket_seq')"))
    return f"TKT-{int(result.scalar()):04d}"


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------
def _message_payload(msg: TicketMessage, include_internal: bool = False) -> dict:
    if msg.is_internal and not include_internal:
        return None
    return {
        "id": msg.id,
        "author_user_id": msg.author_user_id,
        "author_role": msg.author_role,
        "author_name": msg.author_name,
        "kind": msg.kind,
        "is_internal": bool(msg.is_internal),
        "body": msg.body,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    }


def serialize_ticket(ticket: SupportTicket, *, include_internal: bool = False) -> dict:
    """Full ticket payload.

    ``include_internal=True`` is reserved for staff surfaces (admin / owner /
    internal tooling); client surfaces must call the public-message variant
    (``include_internal=False``) so staff notes never leak.
    """
    user = ticket.user
    messages = [_message_payload(m, include_internal) for m in (ticket.messages or [])]
    messages = [m for m in messages if m is not None]

    payload = {
        "id": ticket.id,
        "ticket_number": ticket.ticket_number,
        "user_id": ticket.user_id,
        "subject": ticket.subject,
        "description": ticket.description,
        "category": ticket.category,
        "status": ticket.status,
        "priority": ticket.priority,
        "escalated": bool(ticket.escalated),
        "escalated_by": ticket.escalated_by,
        "escalated_at": ticket.escalated_at.isoformat() if ticket.escalated_at else None,
        "escalation_target": ticket.escalation_target,
        "escalation_reason": ticket.escalation_reason,
        "assignee_id": ticket.assignee_id,
        "assigned_at": ticket.assigned_at.isoformat() if ticket.assigned_at else None,
        "source": ticket.source,
        "admin_reply": ticket.admin_reply,
        "replied_by": ticket.replied_by,
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
        "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
        "closed_at": ticket.closed_at.isoformat() if ticket.closed_at else None,
        "closed_by": ticket.closed_by,
        "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
        "messages": messages,
        "user": {
            "id": user.id,
            "email": user.email,
            "telegram_id": user.telegram_id,
            "telegram_username": user.telegram_username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "language": user.language,
        } if user else None,
    }
    return payload


async def _license_enrichment(session: AsyncSession, tickets) -> dict:
    """One query for active licenses of all listed users (fixes N+1)."""
    user_ids = {t.user_id for t in tickets if t.user_id}
    if not user_ids:
        return {}
    result = await session.execute(
        select(License)
        .where(License.user_id.in_(user_ids), License.status == "active")
    )
    by_user: dict = {}
    for lic in result.scalars().all():
        if lic.user_id not in by_user:  # keep first active license per user
            by_user[lic.user_id] = {"license_key": lic.license_key, "plan": lic.plan}
    return by_user


async def _assignee_names(session: AsyncSession, tickets) -> dict:
    assignee_ids = {t.assignee_id for t in tickets if t.assignee_id}
    if not assignee_ids:
        return {}
    result = await session.execute(select(User).where(User.id.in_(assignee_ids)))
    return {u.id: u for u in result.scalars().all()}


async def serialize_ticket_admin(session: AsyncSession, ticket: SupportTicket) -> dict:
    payload = serialize_ticket(ticket, include_internal=True)
    payload["user"] = {
        "id": ticket.user.id,
        "email": ticket.user.email,
        "telegram_id": ticket.user.telegram_id,
        "telegram_username": ticket.user.telegram_username,
        "first_name": ticket.user.first_name,
        "last_name": ticket.user.last_name,
        "language": ticket.user.language,
        "status": ticket.user.status,
        "created_at": ticket.user.created_at.isoformat() if ticket.user.created_at else None,
    } if ticket.user else None

    lic_map = await _license_enrichment(session, [ticket])
    payload["license"] = lic_map.get(ticket.user_id)

    if ticket.assignee_id:
        assignees = await _assignee_names(session, [ticket])
        a = assignees.get(ticket.assignee_id)
        payload["assignee"] = {
            "id": a.id,
            "first_name": a.first_name,
            "last_name": a.last_name,
            "email": a.email,
            "role": a.role_rel.name if a.role_rel else None,
        } if a else None
    else:
        payload["assignee"] = None
    return payload


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------
async def get_ticket_or_none(session: AsyncSession, ticket_id: str) -> Optional[SupportTicket]:
    result = await session.execute(
        select(SupportTicket)
        .options(selectinload(SupportTicket.user), selectinload(SupportTicket.messages))
        .where(SupportTicket.id == ticket_id)
    )
    return result.scalar_one_or_none()


async def _refresh_conversation(session: AsyncSession, ticket: SupportTicket) -> SupportTicket:
    """Eager-load relationships after a mutation so callers can serialize.

    Accessing ``ticket.messages`` / ``ticket.user`` after a fresh insert would
    trigger an implicit async lazy-load (MissingGreenlet) — the serializer is
    sync by design. Refresh populates both relationships explicitly.
    Detached instances (loaded in an earlier session) are merged first so the
    helper also works for callers that re-attach a previously fetched ticket.
    """
    if ticket.id is not None:
        ticket = await session.merge(ticket)
    await session.refresh(ticket, attribute_names=["user", "messages"])
    return ticket


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
async def create_ticket(
    session: AsyncSession,
    *,
    user: User,
    subject: str,
    description: str,
    category: str = "other",
    priority: str = "medium",
    source: str = "dashboard",
    notify: bool = True,
    client_ref: Optional[str] = None,
) -> SupportTicket:
    """Create a ticket with a race-free number and its opening message.

    The first ``TicketMessage`` duplicates the description so the conversation
    history is complete on every surface (client, Telegram, admin, owner).
    ``client_ref`` overrides the client reference shown in the support email
    (e.g. a Telegram username).
    """
    ticket_number = await allocate_ticket_number(session)
    ticket = SupportTicket(
        user_id=user.id,
        ticket_number=ticket_number,
        subject=subject[:255],
        description=description,
        category=category,
        status="open",
        priority=priority,
        source=source,
    )
    session.add(ticket)
    await session.flush()

    session.add(TicketMessage(
        ticket_id=ticket.id,
        author_user_id=user.id,
        author_role="client",
        author_name=f"{user.first_name or ''} {user.last_name or ''}".strip() or None,
        kind="message",
        is_internal=False,
        body=description,
    ))

    await log_event(
        session, "ticket.created", f"Ticket {ticket_number} created",
        user_id=user.id, source=source, payload={
            "ticket_id": ticket.id, "category": category, "priority": priority,
        },
    )
    await session.commit()

    if notify:
        await _notify_ticket_created(session, ticket, user, category, client_ref=client_ref)

    return await _refresh_conversation(session, ticket)


# ---------------------------------------------------------------------------
# Conversation
# ---------------------------------------------------------------------------
async def add_message(
    session: AsyncSession,
    ticket: SupportTicket,
    *,
    body: str,
    author_user_id: Optional[str] = None,
    author_role: str = "client",
    author_name: Optional[str] = None,
    is_internal: bool = False,
    kind: Optional[str] = None,
    notify: bool = True,
) -> tuple[TicketMessage, str]:
    """Append a message to a ticket's conversation and audit it.

    Public staff replies also update the legacy ``admin_reply`` / ``replied_by``
    columns so pre-existing admin UI and telegram flows keep working.
    Returns the message and the audit entry id.
    """
    msg = TicketMessage(
        ticket_id=ticket.id,
        author_user_id=author_user_id,
        author_role=author_role,
        author_name=author_name,
        kind=kind or ("note" if is_internal else "message"),
        is_internal=is_internal,
        body=body,
    )
    session.add(msg)
    if not is_internal:
        ticket.admin_reply = body
        ticket.replied_by = author_user_id
    ticket.updated_at = _utcnow()
    await session.flush()

    audit_id = await log_event(
        session, "ticket.replied", f"Message added to {ticket.ticket_number}",
        user_id=author_user_id, payload={
            "ticket_id": ticket.id, "message_id": msg.id,
            "is_internal": is_internal, "author_role": author_role,
        },
    )
    await session.commit()

    await _refresh_conversation(session, ticket)
    if notify and not is_internal and author_role != "client":
        await _notify_client_reply(session, ticket, body)
    return msg, audit_id


# ---------------------------------------------------------------------------
# Status / field updates (validated)
# ---------------------------------------------------------------------------
async def update_ticket_fields(
    session: AsyncSession,
    ticket: SupportTicket,
    *,
    fields: dict,
    actor: User,
    actor_role: str,
) -> tuple[dict, str]:
    """Validate and apply whitelisted field updates; audit the result.

    Returns ``(changes, audit_id)``. ``resolved`` / ``closed`` statuses set
    the corresponding timestamps; reopening clears ``resolved_at``/``closed_at``.
    """
    allowed = {"status", "priority", "category", "assignee_id"}
    changes: dict = {}
    now = _utcnow()

    for key in allowed:
        if key not in fields or fields[key] is None:
            continue
        value = fields[key]
        if key == "status":
            if value not in TICKET_STATUSES:
                raise ValueError(f"Invalid status: {value}")
        elif key == "priority":
            if value not in TICKET_PRIORITIES:
                raise ValueError(f"Invalid priority: {value}")
        elif key == "category":
            if value not in TICKET_CATEGORIES:
                raise ValueError(f"Invalid category: {value}")
        elif key == "assignee_id":
            # Falsy value means "unassign" — normalize to None so the column
            # stores NULL rather than an empty string.
            value = value or None
            if value:
                check = await session.execute(select(User.id).where(User.id == value))
                if check.scalar_one_or_none() is None:
                    raise ValueError("Assignee does not exist")
                if value == ticket.assignee_id:
                    continue
            elif not ticket.assignee_id:
                continue

        setattr(ticket, key, value)
        changes[key] = value
        if key == "assignee_id":
            ticket.assigned_at = now if value else None

    if "status" in changes:
        if ticket.status == "resolved":
            ticket.resolved_at = now
        elif ticket.status == "closed":
            ticket.closed_at = now
            ticket.closed_by = actor.id
        elif ticket.status == "open":
            ticket.resolved_at = None
            ticket.closed_at = None
            ticket.closed_by = None

    if not changes:
        return {}, ""

    ticket.updated_at = now
    audit_id = await log_event(
        session, "ticket.updated", f"Ticket {ticket.ticket_number} updated",
        user_id=actor.id, source="web", payload={"changes": changes},
    )
    await session.commit()
    return changes, audit_id


# ---------------------------------------------------------------------------
# Escalation
# ---------------------------------------------------------------------------
async def escalate_ticket(
    session: AsyncSession,
    ticket: SupportTicket,
    *,
    actor: User,
    target: str,
    reason: str,
    notify: bool = True,
) -> str:
    """Escalate a ticket to a staff role (developer / admin / owner).

    Records who escalated, when, to whom and why — escalation metadata was
    previously dropped (``escalated_by`` was never written).
    Returns the audit id.
    """
    if target not in ESCALATION_TARGETS:
        raise ValueError(f"Invalid escalation target: {target}")
    now = _utcnow()
    ticket.escalated = True
    ticket.priority = "urgent"
    ticket.escalated_by = actor.id
    ticket.escalated_at = now
    ticket.escalation_target = target
    ticket.escalation_reason = reason
    ticket.updated_at = now
    audit_id = await log_event(
        session, "ticket.escalated", f"Ticket {ticket.ticket_number} escalated to {target}",
        user_id=actor.id, source="web", severity="WARNING",
        payload={"ticket_id": ticket.id, "target": target, "reason": reason},
    )
    await session.commit()

    if notify:
        await _notify_ticket_escalated(session, ticket, target, reason)
    return audit_id


# ---------------------------------------------------------------------------
# Ban  (owner-only permission enforced at the route layer)
# ---------------------------------------------------------------------------
async def ban_ticket_user(
    session: AsyncSession,
    ticket: SupportTicket,
    *,
    actor: User,
) -> str:
    """Ban the ticket owner: suspend all active licenses and close the ticket.

    This is a capital-protection action; the audit trail is mandatory and the
    marker is appended to the ticket for transparency. Returns the audit id.
    """
    lic_result = await session.execute(
        select(License).where(License.user_id == ticket.user_id, License.status == "active")
    )
    suspended = 0
    for lic in lic_result.scalars().all():
        lic.status = "suspended"
        suspended += 1

    ticket.status = "closed"
    ticket.closed_at = _utcnow()
    ticket.closed_by = actor.id
    ticket.resolved_at = None
    ticket.updated_at = _utcnow()
    ticket.admin_reply = (ticket.admin_reply or "") + "\n\n[User banned by admin]"

    audit_id = await log_event(
        session, "ticket.user_banned", f"User {ticket.user_id} banned via ticket {ticket.ticket_number}",
        user_id=actor.id, source="web", severity="CRITICAL",
        payload={"ticket_id": ticket.id, "user_id": ticket.user_id, "licenses_suspended": suspended},
    )
    await session.commit()
    return audit_id


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------
async def list_tickets_for_user(
    session: AsyncSession,
    user_id: str,
    *,
    status: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
):
    query = (
        select(SupportTicket)
        .options(selectinload(SupportTicket.user), selectinload(SupportTicket.messages))
        .where(SupportTicket.user_id == user_id)
        .order_by(SupportTicket.created_at.desc())
    )
    count_q = select(func.count(SupportTicket.id)).where(SupportTicket.user_id == user_id)
    if status in TICKET_STATUSES:
        query = query.where(SupportTicket.status == status)
        count_q = count_q.where(SupportTicket.status == status)

    total = (await session.execute(count_q)).scalar() or 0
    result = await session.execute(query.offset((page - 1) * limit).limit(limit))
    return list(result.scalars().all()), total


async def list_tickets_admin(
    session: AsyncSession,
    *,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    category: Optional[str] = None,
    escalated: Optional[bool] = None,
    assignee_id: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
):
    """Staff listing with filters; resolves license + assignee in bulk."""
    query = (
        select(SupportTicket)
        .options(selectinload(SupportTicket.user), selectinload(SupportTicket.messages))
        .order_by(SupportTicket.created_at.desc())
    )
    count_q = select(func.count(SupportTicket.id))

    def _apply(q):
        if status in TICKET_STATUSES:
            q = q.where(SupportTicket.status == status)
        if priority in TICKET_PRIORITIES:
            q = q.where(SupportTicket.priority == priority)
        if category in TICKET_CATEGORIES:
            q = q.where(SupportTicket.category == category)
        if escalated is not None:
            q = q.where(SupportTicket.escalated == escalated)
        if assignee_id:
            q = q.where(SupportTicket.assignee_id == assignee_id)
        if search:
            like = f"%{search}%"
            q = q.where(or_(
                SupportTicket.subject.ilike(like),
                SupportTicket.description.ilike(like),
                SupportTicket.ticket_number.ilike(like),
            ))
        return q

    query = _apply(query)
    count_q = _apply(count_q)

    total = (await session.execute(count_q)).scalar() or 0
    result = await session.execute(query.offset((page - 1) * limit).limit(limit))
    tickets = list(result.scalars().all())

    lic_map = await _license_enrichment(session, tickets)
    assignees = await _assignee_names(session, tickets)

    items = []
    for t in tickets:
        d = serialize_ticket(t, include_internal=True)
        d["license"] = lic_map.get(t.user_id)
        if t.assignee_id:
            a = assignees.get(t.assignee_id)
            d["assignee"] = {
                "id": a.id, "first_name": a.first_name, "last_name": a.last_name,
                "email": a.email, "role": a.role_rel.name if a.role_rel else None,
            } if a else None
        else:
            d["assignee"] = None
        items.append(d)
    return items, total


async def ticket_metrics(session: AsyncSession, *, assignee_id: Optional[str] = None) -> dict:
    """Support workload metrics for the owner portal."""
    base = [SupportTicket.user_id.isnot(None)]
    if assignee_id:
        base.append(SupportTicket.assignee_id == assignee_id)

    counts = {
        "total": 0, "open": 0, "in_progress": 0, "resolved": 0, "closed": 0,
        "escalated": 0, "urgent": 0,
    }
    result = await session.execute(select(SupportTicket).where(*base))
    for t in result.scalars().all():
        counts["total"] += 1
        if t.status in counts:
            counts[t.status] += 1
        if t.escalated:
            counts["escalated"] += 1
        if t.priority == "urgent":
            counts["urgent"] += 1

    # Average first-response time (created -> first staff public message)
    resp: list[float] = []
    for t in (await session.execute(
        select(SupportTicket)
        .options(selectinload(SupportTicket.messages))
        .where(*base)
    )).scalars().all():
        for m in (t.messages or []):
            if m.is_internal or m.author_role == "client":
                continue
            if m.created_at and t.created_at:
                resp.append((m.created_at - t.created_at).total_seconds())
                break
    counts["avg_first_response_hours"] = round(sum(resp) / len(resp) / 3600, 1) if resp else None
    return counts


# ---------------------------------------------------------------------------
# Notifications (best-effort; never raise)
# ---------------------------------------------------------------------------
async def _notify_ticket_created(session, ticket, user, category, client_ref: str = "") -> None:
    try:
        from api.services.email_service import notify_support_ticket
        if not client_ref:
            client_ref = f"{user.first_name or ''} {user.last_name or ''}".strip()
            client_ref += f" ({user.email})" if user.email else ""
        await notify_support_ticket(
            subject=f"{ticket.ticket_number} — {category}",
            body=ticket.description,
            session=session,
            client_ref=client_ref,
            category=category,
        )
    except Exception as e:
        logger.warning("Ticket-created email failed (ticket=%s): %s", ticket.ticket_number, e)


async def _notify_client_reply(session, ticket, reply_text) -> None:
    """Push a staff reply to the client via Telegram (escaped, localized)."""
    if not (ticket.user and ticket.user.telegram_id):
        return
    try:
        from telegram_bot.api_client import telegram_application
        bot = telegram_application.app.bot
        lang = (ticket.user.language or "EN").upper()
        safe = _escape(reply_text)
        safe_num = _escape(ticket.ticket_number)
        safe_cat = _escape(ticket.category)
        msg = {
            "EN": (
                f"📩 <b>Reply to your ticket</b>\n\n"
                f"Ticket: <b>{safe_num}</b>\nCategory: {safe_cat}\n\n"
                f"<b>Support reply:</b>\n{safe}\n\n"
                f"You can reply to this ticket from the dashboard or Telegram."
            ),
            "AR": (
                f"📩 <b>رد على تذكرتك</b>\n\n"
                f"التذكرة: <b>{safe_num}</b>\nالفئة: {safe_cat}\n\n"
                f"<b>رد الدعم:</b>\n{safe}\n\n"
                f"يمكنك الرد على هذه التذكرة من لوحة التحكم أو تيليجرام."
            ),
            "FR": (
                f"📩 <b>Réponse à votre ticket</b>\n\n"
                f"Ticket: <b>{safe_num}</b>\nCatégorie: {safe_cat}\n\n"
                f"<b>Réponse du support:</b>\n{safe}\n\n"
                f"Vous pouvez répondre depuis le tableau de bord ou Telegram."
            ),
            "ES": (
                f"📩 <b>Respuesta a tu ticket</b>\n\n"
                f"Ticket: <b>{safe_num}</b>\nCategoría: {safe_cat}\n\n"
                f"<b>Respuesta del soporte:</b>\n{safe}\n\n"
                f"Puedes responder desde el panel o Telegram."
            ),
        }
        await bot.send_message(chat_id=int(ticket.user.telegram_id), text=msg.get(lang, msg["EN"]), parse_mode="HTML")
        logger.info("Ticket reply pushed to user %s", ticket.user.id)
    except Exception as e:
        logger.warning("Telegram reply push failed (ticket=%s): %s", ticket.ticket_number, e)


async def _notify_ticket_escalated(session, ticket, target, reason) -> None:
    try:
        from api.services.email_service import _get_config, send_email
        cfg = await _get_config(session)
        text = (
            f"Escalated ticket {ticket.ticket_number}\n\n"
            f"Escalated to: {target}\nReason: {reason}\n\n"
            f"Subject: {ticket.subject}\n{ticket.description}"
        )
        await send_email(cfg["support_address"], f"Escalated — {ticket.ticket_number}", text, session=session)
    except Exception as e:
        logger.warning("Escalation email failed (ticket=%s): %s", ticket.ticket_number, e)

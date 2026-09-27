"""Support/ticket menu pages for the Telegram bot.

Renders the shared ticket records (via ``telegram_bot.services.support_service``)
in 4 languages. All dynamic content is HTML-escaped before embedding into
``parse_mode=HTML`` messages to prevent Telegram HTML injection.
"""
from __future__ import annotations

import html
import logging
from datetime import datetime, timezone

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database.db import async_session_factory
from database.repositories import UserRepository
from telegram_bot.services.support_service import (
    get_my_ticket,
    list_my_tickets,
)
from telegram_bot.ui.callbacks import Callback
from telegram_bot.ui.icons import Icons
from telegram_bot.ui.keyboards.support import (
    status_label,
    support_home_keyboard,
    ticket_cancel_keyboard,
    ticket_detail_keyboard,
    ticket_list_keyboard,
)

logger = logging.getLogger(__name__)


def _msg(lang: str, d: dict) -> str:
    return d.get(lang, d["EN"])


def _fmt_dt(dt) -> str:
    if not dt:
        return "—"
    return dt.strftime("%Y-%m-%d %H:%M")


def _esc(value) -> str:
    return html.escape(str(value or ""), quote=False)


def _badge(status: str, lang: str) -> str:
    return status_label(status, lang)


async def _resolve_user(context: ContextTypes.DEFAULT_TYPE, tg_id: int):
    async with async_session_factory() as session:
        repo = UserRepository(session)
        return await repo.get_by_telegram_id(tg_id)


# ---------------------------------------------------------------------------
# My Tickets (list)
# ---------------------------------------------------------------------------
async def render_my_tickets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    lang = context.user_data.get("language", "EN")
    tg_user = update.effective_user

    user = await _resolve_user(context, tg_user.id)
    if not user:
        text = _msg(lang, {
            "EN": f"{Icons.ERROR} <b>User not found.</b> Use /start first.",
            "AR": f"{Icons.ERROR} <b>المستخدم غير موجود.</b> استخدم /start أولاً.",
            "FR": f"{Icons.ERROR} <b>Utilisateur introuvable.</b> Utilisez /start d'abord.",
            "ES": f"{Icons.ERROR} <b>Usuario no encontrado.</b> Usa /start primero.",
        })
        await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=support_home_keyboard(lang))
        return

    async with async_session_factory() as session:
        tickets = await list_my_tickets(session, user.id)

    if not tickets:
        text = _msg(lang, {
            "EN": (
                f"{Icons.SUPPORT} <b>My Tickets</b>\n\n"
                f"You have no tickets yet. Create one and our team will respond within 24h."
            ),
            "AR": (
                f"{Icons.SUPPORT} <b>تذاكري</b>\n\n"
                f"لا توجد تذاكر بعد. أنشئ تذكرة وسوف يرد فريقنا خلال 24 ساعة."
            ),
            "FR": (
                f"{Icons.SUPPORT} <b>Mes Tickets</b>\n\n"
                f"Vous n'avez aucun ticket. Créez-en un, notre équipe répondra sous 24h."
            ),
            "ES": (
                f"{Icons.SUPPORT} <b>Mis Tickets</b>\n\n"
                f"No tienes tickets aún. Crea uno y responderemos dentro de 24h."
            ),
        })
        await query.edit_message_text(
            text=text, parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    _msg(lang, {"EN": "📩 Create Ticket", "AR": "📩 إنشاء تذكرة", "FR": "📩 Créer un Ticket", "ES": "📩 Crear Ticket"}),
                    callback_data=Callback.TICKET_CREATE
                )],
                [InlineKeyboardButton(
                    _msg(lang, {"EN": "⬅️ Back", "AR": "⬅️ رجوع", "FR": "⬅️ Retour", "ES": "⬅️ Volver"}),
                    callback_data=Callback.MENU_SUPPORT
                )],
            ]),
        )
        return

    lines = [f"{Icons.SUPPORT} <b>My Tickets</b>\n"]
    for t in tickets[:10]:
        safe_subject = _esc(t.subject)
        lines.append(f"• {_esc(t.ticket_number)} — {safe_subject} · {_badge(t.status, lang)}")
    text = "\n".join(lines) + _msg(lang, {
        "EN": "\n\nTap a ticket to open it.",
        "AR": "\n\nاضغط على تذكرة لفتحها.",
        "FR": "\n\nAppuyez sur un ticket pour l'ouvrir.",
        "ES": "\n\nToca un ticket para abrirlo.",
    })
    await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=ticket_list_keyboard(tickets[:10], lang))


# ---------------------------------------------------------------------------
# Ticket detail (conversation, public messages only)
# ---------------------------------------------------------------------------
async def render_ticket_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, ticket_id: str):
    query = update.callback_query
    lang = context.user_data.get("language", "EN")
    tg_user = update.effective_user

    user = await _resolve_user(context, tg_user.id)
    if not user:
        text = _msg(lang, {
            "EN": f"{Icons.ERROR} <b>User not found.</b> Use /start first.",
            "AR": f"{Icons.ERROR} <b>المستخدم غير موجود.</b> استخدم /start أولاً.",
            "FR": f"{Icons.ERROR} <b>Utilisateur introuvable.</b> Utilisez /start d'abord.",
            "ES": f"{Icons.ERROR} <b>Usuario no encontrado.</b> Usa /start primero.",
        })
        await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=support_home_keyboard(lang))
        return

    async with async_session_factory() as session:
        ticket = await get_my_ticket(session, user.id, ticket_id)

    if not ticket:
        text = _msg(lang, {
            "EN": f"{Icons.ERROR} <b>Ticket not found.</b>",
            "AR": f"{Icons.ERROR} <b>التذكرة غير موجودة.</b>",
            "FR": f"{Icons.ERROR} <b>Ticket introuvable.</b>",
            "ES": f"{Icons.ERROR} <b>Ticket no encontrado.</b>",
        })
        await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=ticket_cancel_keyboard(lang))
        return

    safe_num = _esc(ticket.ticket_number)
    safe_subject = _esc(ticket.subject)
    safe_cat = _esc(ticket.category)
    header = (
        f"{Icons.SUPPORT} <b>Ticket {safe_num}</b>\n"
        f"{_esc(ticket.created_at.strftime('%Y-%m-%d %H:%M') if ticket.created_at else '—')} · {_badge(ticket.status, lang)}\n"
        f"Category: {safe_cat}\n"
        f"Priority: {_esc(ticket.priority)}\n"
    )
    if ticket.escalated:
        header += _msg(lang, {
            "EN": "🚨 <b>Escalated</b>\n",
            "AR": "🚨 <b>تم التصعيد</b>\n",
            "FR": "🚨 <b>Escaladé</b>\n",
            "ES": "🚨 <b>Escalado</b>\n",
        })

    parts = [header, f"<b>{safe_subject}</b>\n"]
    for m in (ticket.messages or []):
        if m.is_internal:  # staff notes never reach the client
            continue
        who = _esc(m.author_name or m.author_role)
        parts.append(f"<i>{who} · {_esc(m.created_at.strftime('%Y-%m-%d %H:%M') if m.created_at else '—')}</i>\n{_esc(m.body)}")
    text = "\n\n".join(parts)

    allow_reply = ticket.status != "closed"
    await query.edit_message_text(
        text=text, parse_mode="HTML",
        reply_markup=ticket_detail_keyboard(ticket.id, lang, allow_reply=allow_reply),
    )


# ---------------------------------------------------------------------------
# Start reply flow
# ---------------------------------------------------------------------------
async def start_ticket_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, ticket_id: str):
    query = update.callback_query
    lang = context.user_data.get("language", "EN")
    tg_user = update.effective_user

    user = await _resolve_user(context, tg_user.id)
    if not user:
        await query.answer(_msg(lang, {
            "EN": "Use /start first",
            "AR": "استخدم /start أولاً",
            "FR": "Utilisez /start d'abord",
            "ES": "Usa /start primero",
        }))
        return

    async with async_session_factory() as session:
        ticket = await get_my_ticket(session, user.id, ticket_id)

    if not ticket:
        await query.answer(_msg(lang, {
            "EN": "Ticket not found",
            "AR": "التذكرة غير موجودة",
            "FR": "Ticket introuvable",
            "ES": "Ticket no encontrado",
        }))
        return
    if ticket.status == "closed":
        text = _msg(lang, {
            "EN": f"{Icons.ERROR} This ticket is closed. Create a new ticket if you need further help.",
            "AR": f"{Icons.ERROR} هذه التذكرة مغلقة. أنشئ تذكرة جديدة إذا كنت بحاجة لمزيد من المساعدة.",
            "FR": f"{Icons.ERROR} Ce ticket est fermé. Créez un nouveau ticket si vous avez besoin d'aide.",
            "ES": f"{Icons.ERROR} Este ticket está cerrado. Crea un nuevo ticket si necesitas ayuda.",
        })
        await query.edit_message_text(
            text=text, parse_mode="HTML",
            reply_markup=ticket_detail_keyboard(ticket.id, lang, allow_reply=False),
        )
        return

    context.user_data["waiting_for"] = "TICKET_REPLY"
    context.user_data["ticket_reply_id"] = ticket.id
    text = _msg(lang, {
        "EN": (
            f"{Icons.SUPPORT} <b>Reply to {ticket.ticket_number}</b>\n\n"
            f"Type your message below. It will be added to the ticket conversation."
        ),
        "AR": (
            f"{Icons.SUPPORT} <b>رد على {ticket.ticket_number}</b>\n\n"
            f"اكتب رسالتك بالأسفل. ستُضاف إلى محادثة التذكرة."
        ),
        "FR": (
            f"{Icons.SUPPORT} <b>Répondre à {ticket.ticket_number}</b>\n\n"
            f"Tapez votre message ci-dessous. Il sera ajouté à la conversation."
        ),
        "ES": (
            f"{Icons.SUPPORT} <b>Responder a {ticket.ticket_number}</b>\n\n"
            f"Escribe tu mensaje abajo. Se añadirá a la conversación del ticket."
        ),
    })
    await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=ticket_cancel_keyboard(lang, back_callback=f"{Callback.TICKET_VIEW}{ticket.id}"))


async def handle_ticket_status_filter(update: Update, context: ContextTypes.DEFAULT_TYPE, status: str):
    """TICKET:STATUS:{status} — reuses the list view with a status filter."""
    query = update.callback_query
    lang = context.user_data.get("language", "EN")
    tg_user = update.effective_user

    user = await _resolve_user(context, tg_user.id)
    if not user:
        return
    async with async_session_factory() as session:
        tickets = await list_my_tickets(session, user.id, status=status if status != "all" else None)

    if not tickets:
        text = _msg(lang, {
            "EN": f"{Icons.INFO} No tickets with this status.",
            "AR": f"{Icons.INFO} لا توجد تذاكر بهذه الحالة.",
            "FR": f"{Icons.INFO} Aucun ticket avec ce statut.",
            "ES": f"{Icons.INFO} No hay tickets con este estado.",
        })
        await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=ticket_cancel_keyboard(lang))
        return
    await render_my_tickets(update, context)

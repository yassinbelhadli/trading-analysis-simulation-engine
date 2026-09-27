"""Support/ticket inline keyboards for the Telegram bot.

Label strings are kept here (4 languages) — no business logic.
"""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from telegram_bot.ui.callbacks import Callback

_B = {
    "create_ticket": {"EN": "📩 Create Ticket", "AR": "📩 إنشاء تذكرة", "FR": "📩 Créer un Ticket", "ES": "📩 Crear Ticket"},
    "my_tickets": {"EN": "🎫 My Tickets", "AR": "🎫 تذاكري", "FR": "🎫 Mes Tickets", "ES": "🎫 Mis Tickets"},
    "reply": {"EN": "💬 Reply", "AR": "💬 رد", "FR": "💬 Répondre", "ES": "💬 Responder"},
    "back": {"EN": "⬅️ Back", "AR": "⬅️ رجوع", "FR": "⬅️ Retour", "ES": "⬅️ Volver"},
    "back_tickets": {"EN": "⬅️ My Tickets", "AR": "⬅️ تذاكري", "FR": "⬅️ Mes Tickets", "ES": "⬅️ Mis Tickets"},
    "back_support": {"EN": "⬅️ Support", "AR": "⬅️ الدعم", "FR": "⬅️ Support", "ES": "⬅️ Soporte"},
    "open": {"EN": "🟢 Open", "AR": "🟢 مفتوحة", "FR": "🟢 Ouvert", "ES": "🟢 Abierta"},
    "in_progress": {"EN": "🟡 In Progress", "AR": "🟡 قيد المعالجة", "FR": "🟡 En cours", "ES": "🟡 En progreso"},
    "resolved": {"EN": "🔵 Resolved", "AR": "🔵 تم الحل", "FR": "🔵 Résolu", "ES": "🔵 Resuelta"},
    "closed": {"EN": "⚪ Closed", "AR": "⚪ مغلقة", "FR": "⚪ Fermé", "ES": "⚪ Cerrada"},
    "filter": {"EN": "🗂 Filter by Status", "AR": "🗂 تصفية حسب الحالة", "FR": "🗂 Filtrer par statut", "ES": "🗂 Filtrar por estado"},
    "all": {"EN": "📋 All", "AR": "📋 الكل", "FR": "📋 Tous", "ES": "📋 Todos"},
}


def _label(key: str, lang: str) -> str:
    return _B[key].get(lang, _B[key]["EN"])


def status_label(status: str, lang: str) -> str:
    return _B.get(status, {}).get(lang, _B.get(status, {}).get("EN", status))


def support_home_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(_label("create_ticket", lang), callback_data=Callback.TICKET_CREATE)],
        [InlineKeyboardButton(_label("my_tickets", lang), callback_data=Callback.TICKET_LIST)],
        [InlineKeyboardButton(_label("back", lang), callback_data=Callback.NAV_BACK)],
    ])


def ticket_list_keyboard(tickets, lang: str) -> InlineKeyboardMarkup:
    rows = []
    for t in tickets:
        label = f"{t.ticket_number} • {status_label(t.status, lang)}"
        rows.append([
            InlineKeyboardButton(label, callback_data=f"{Callback.TICKET_VIEW}{t.id}")
        ])
    rows.append([
        InlineKeyboardButton(_label("back_support", lang), callback_data=Callback.MENU_SUPPORT)
    ])
    return InlineKeyboardMarkup(rows)


def ticket_detail_keyboard(ticket_id: str, lang: str, *, allow_reply: bool = True) -> InlineKeyboardMarkup:
    rows = []
    if allow_reply:
        rows.append([InlineKeyboardButton(_label("reply", lang), callback_data=f"{Callback.TICKET_REPLY}{ticket_id}")])
    rows.append([InlineKeyboardButton(_label("back_tickets", lang), callback_data=Callback.TICKET_LIST)])
    return InlineKeyboardMarkup(rows)


def ticket_cancel_keyboard(lang: str, *, back_callback: str = Callback.TICKET_LIST) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(_label("back", lang), callback_data=back_callback)]
    ])

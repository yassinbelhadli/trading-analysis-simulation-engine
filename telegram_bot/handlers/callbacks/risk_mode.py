import logging

from telegram import Update
from telegram.ext import ContextTypes

from database.db import async_session_factory
from database.repositories import AccountRepository, UserRepository
from database.models import RiskProfile
from telegram_bot.ui.keyboards.risk_mode import risk_mode_keyboard, risk_mode_select_keyboard
from telegram_bot.ui.keyboards.accounts import account_detail_keyboard
from core_engine.engine_manager import engine_manager
from core_engine.audit.audit_logger import audit_logger
from core_engine.events.event_types import EventType

logger = logging.getLogger(__name__)

MODE_LABELS = {
    "ultra_conservative": {"EN": "🛡️ Ultra Conservative", "FR": "🛡️ Ultra Conservative", "AR": "🛡️ فائق الحذر", "ES": "🛡️ Ultra Conservador"},
    "conservative": {"EN": "🔵 Conservative", "FR": "🔵 Conservative", "AR": "🔵 محافظ", "ES": "🔵 Conservador"},
    "balanced": {"EN": "🟡 Balanced", "FR": "🟡 Équilibré", "AR": "🟡 متوازن", "ES": "🟡 Equilibrado"},
    "aggressive": {"EN": "🔴 Aggressive", "FR": "🔴 Agressif", "AR": "🔴 هجومي", "ES": "🔴 Agresivo"},
}

MODE_RISK_PCT = {
    "ultra_conservative": 0.10,
    "conservative": 0.25,
    "balanced": 0.50,
    "aggressive": 1.00,
}


async def handle_risk_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    lang = context.user_data.get("language", "EN")
    account_id = query.data.split(":")[-1]

    async with async_session_factory() as session:
        repo = AccountRepository(session)
        account = await repo.get_by_id(account_id)
        if not account or not account.risk_profile:
            await query.edit_message_text("❌ Account or risk profile not found.")
            return

        current_mode = account.risk_profile.mode or "balanced"
        await query.edit_message_text(
            text=_text(lang, "TITLE", current_mode),
            parse_mode="HTML",
            reply_markup=risk_mode_keyboard(account_id, current_mode, lang),
        )


_MODE_CODE = {"u": "ultra_conservative", "c": "conservative", "b": "balanced", "a": "aggressive"}

async def handle_risk_mode_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    lang = context.user_data.get("language", "EN")
    parts = query.data.split(":")
    account_id = parts[1]
    pending_mode = _MODE_CODE[parts[2]]

    await query.edit_message_text(
        text=_text(lang, "CONFIRM", pending_mode),
        parse_mode="HTML",
        reply_markup=risk_mode_select_keyboard(account_id, pending_mode, lang),
    )


async def handle_risk_mode_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    lang = context.user_data.get("language", "EN")
    parts = query.data.split(":")
    account_id = parts[1]
    new_mode = _MODE_CODE[parts[2]]

    async with async_session_factory() as session:
        repo = AccountRepository(session)
        account = await repo.get_by_id(account_id)
        if not account or not account.risk_profile:
            await query.edit_message_text("❌ Account or risk profile not found.")
            return

        old_mode = account.risk_profile.mode or "balanced"
        account.risk_profile.mode = new_mode
        account.risk_profile.max_risk_trade = MODE_RISK_PCT[new_mode]
        await session.commit()

        # audit log
        await audit_logger.log_risk(
            action=EventType.RISK_CHECK.value,
            message=f"Risk mode changed: {old_mode} -> {new_mode}",
            account_id=account_id,
            user_id=account.user_id,
            payload={"old_mode": old_mode, "new_mode": new_mode, "risk_per_trade": MODE_RISK_PCT[new_mode]},
        )

        old_label = MODE_LABELS.get(old_mode, {}).get(lang, old_mode)
        new_label = MODE_LABELS.get(new_mode, {}).get(lang, new_mode)
        await query.edit_message_text(
            text=_text(lang, "CHANGED", old_label, new_label),
            parse_mode="HTML",
            reply_markup=account_detail_keyboard(account_id, account.engine_status, engine_manager.is_running(account_id), lang),
        )


async def handle_risk_mode_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    lang = context.user_data.get("language", "EN")
    account_id = query.data.split(":")[-1]

    async with async_session_factory() as session:
        repo = AccountRepository(session)
        account = await repo.get_by_id(account_id)
        if not account:
            await query.edit_message_text("❌ Account not found.")
            return

        await query.edit_message_text(
            text=_text(lang, "CANCELLED"),
            parse_mode="HTML",
            reply_markup=account_detail_keyboard(account_id, account.engine_status, engine_manager.is_running(account_id), lang),
        )


def _text(lang: str, key: str, mode: str = "", mode2: str = "") -> str:
    MODE = MODE_LABELS
    risk_pct = MODE_RISK_PCT
    texts = {
        "TITLE": {
            "EN": f"<b>⚙ Risk Mode</b>\n\nCurrent mode: <b>{{}}</b>\n\nChoose your risk level:",
            "FR": f"<b>⚙ Mode risque</b>\n\nMode actuel : <b>{{}}</b>\n\nChoisissez votre niveau de risque :",
            "AR": f"<b>⚙ وضع المخاطرة</b>\n\nالوضع الحالي: <b>{{}}</b>\n\nاختر مستوى المخاطرة:",
            "ES": f"<b>⚙ Modo de riesgo</b>\n\nModo actual: <b>{{}}</b>\n\nElige tu nivel de riesgo:",
        },
        "CONFIRM": {
            "EN": f"<b>⚙ Change Risk Mode</b>\n\nAre you sure you want to switch to <b>{{}}</b> ({{}}% per trade)?",
            "FR": f"<b>⚙ Changer le mode risque</b>\n\nÊtes-vous sûr de vouloir passer à <b>{{}}</b> ({{}}% par trade)?",
            "AR": f"<b>⚙ تغيير وضع المخاطرة</b>\n\nهل أنت متأكد من التغيير إلى <b>{{}}</b> ({{}}% لكل صفقة)؟",
            "ES": f"<b>⚙ Cambiar modo de riesgo</b>\n\n¿Estás seguro de cambiar a <b>{{}}</b> ({{}}% por operación)?",
        },
        "CHANGED": {
            "EN": f"✅ <b>Risk mode changed</b>\n\n<code>{{}} → {{}}</code>",
            "FR": f"✅ <b>Mode risque modifié</b>\n\n<code>{{}} → {{}}</code>",
            "AR": f"✅ <b>تم تغيير وضع المخاطرة</b>\n\n<code>{{}} → {{}}</code>",
            "ES": f"✅ <b>Modo de riesgo cambiado</b>\n\n<code>{{}} → {{}}</code>",
        },
        "CANCELLED": {
            "EN": "❌ Cancelled. Risk mode unchanged.",
            "FR": "❌ Annulé. Mode risque inchangé.",
            "AR": "❌ تم الإلغاء. وضع المخاطرة لم يتغير.",
            "ES": "❌ Cancelado. Modo de riesgo sin cambios.",
        },
    }
    t = texts.get(key, {}).get(lang, texts.get(key, {}).get("EN", key))
    if key == "TITLE":
        mode_name = MODE.get(mode, {}).get(lang, mode)
        return t.format(mode_name)
    if key == "CONFIRM":
        mode_name = MODE.get(mode, {}).get(lang, mode)
        return t.format(mode_name, risk_pct.get(mode, 0.5))
    if key == "CHANGED":
        return t.format(mode, mode2)
    return t

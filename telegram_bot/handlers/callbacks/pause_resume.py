from telegram import Update
from telegram.ext import ContextTypes

from database.db import async_session_factory
from database.repositories import AccountRepository, UserRepository
from core_engine.account_manager import AccountManager
from core_engine.engine_manager import engine_manager
from telegram_bot.ui.keyboards.accounts import account_detail_keyboard
from telegram_bot.services.navigation import push_page, PAGE_ACCOUNT_DETAIL


async def _resolve_owned_account(update: Update, account_id: str):
    """Return (user, account) when the Telegram user owns the account.

    Ownership check is mandatory for every account-scoped bot action: a
    Telegram user must never control another client's trading account. The
    same rule already exists in account_detail.py.
    """
    async with async_session_factory() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(update.effective_user.id)
        if not user:
            return None, None
        acc_repo = AccountRepository(session)
        account = await acc_repo.get_by_id(account_id)
        if not account or account.user_id != user.id:
            return None, None
        return user, account


async def handle_account_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    lang = context.user_data.get("language", "EN")
    account_id = query.data.rsplit(":", 1)[1] if ":" in query.data else ""

    user, account = await _resolve_owned_account(update, account_id)
    if not user or not account:
        await query.edit_message_text("❌ Account not found.")
        return

    async with async_session_factory() as session:
        mgr = AccountManager(session)
        try:
            await mgr.pause_account(account_id)
            await session.commit()
        except Exception:
            await session.rollback()
            await query.edit_message_text("❌ Failed to pause account.")
            return

    # stop engine in memory
    if engine_manager.is_running(account_id):
        await engine_manager.pause(account_id)

    await query.edit_message_text(
        text=_msg(lang, "PAUSED"),
        parse_mode="HTML",
        reply_markup=account_detail_keyboard(account_id, "PAUSED", False, lang),
    )


async def handle_account_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    lang = context.user_data.get("language", "EN")
    account_id = query.data.rsplit(":", 1)[1] if ":" in query.data else ""

    user, account = await _resolve_owned_account(update, account_id)
    if not user or not account:
        await query.edit_message_text("❌ Account not found.")
        return

    async with async_session_factory() as session:
        mgr = AccountManager(session)
        try:
            await mgr.resume_account(account_id)
            await session.commit()
        except Exception:
            await session.rollback()
            await query.edit_message_text("❌ Failed to resume account.")
            return

    # resume engine in memory
    await engine_manager.start(account_id)

    await query.edit_message_text(
        text=_msg(lang, "RESUMED"),
        parse_mode="HTML",
        reply_markup=account_detail_keyboard(account_id, "ACTIVE", True, lang),
    )


async def handle_account_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    lang = context.user_data.get("language", "EN")
    account_id = query.data.rsplit(":", 1)[-1] if ":" in query.data else ""

    user, account = await _resolve_owned_account(update, account_id)
    if not user or not account:
        await query.edit_message_text("❌ Account not found.")
        return

    await engine_manager.start(account_id)

    push_page(context, PAGE_ACCOUNT_DETAIL)
    await query.edit_message_text(
        text=_msg(lang, "STARTED"),
        parse_mode="HTML",
        reply_markup=account_detail_keyboard(account_id, "ACTIVE", True, lang),
    )


async def handle_account_restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    lang = context.user_data.get("language", "EN")
    account_id = query.data.rsplit(":", 1)[-1] if ":" in query.data else ""

    user, account = await _resolve_owned_account(update, account_id)
    if not user or not account:
        await query.edit_message_text("❌ Account not found.")
        return

    await engine_manager.restart(account_id)
    push_page(context, PAGE_ACCOUNT_DETAIL)
    runtime_status = engine_manager.is_running(account_id)

    await query.edit_message_text(
        text=_msg(lang, "RESTARTED"),
        parse_mode="HTML",
        reply_markup=account_detail_keyboard(account_id, "ACTIVE", runtime_status, lang),
    )


def _msg(lang: str, key: str) -> str:
    msgs = {
        "PAUSED": {
            "EN": "⏸ <b>Account Paused</b>\n\nThe engine has been paused.",
            "FR": "⏸ <b>Compte en pause</b>\n\nLe moteur a été mis en pause.",
            "AR": "⏸ <b>تم إيقاف الحساب مؤقتاً</b>\n\nتم إيقاف المحرك.",
            "ES": "⏸ <b>Cuenta pausada</b>\n\nEl motor ha sido pausado.",
        },
        "RESUMED": {
            "EN": "▶ <b>Account Resumed</b>\n\nThe engine is running again.",
            "FR": "▶ <b>Compte repris</b>\n\nLe moteur est à nouveau actif.",
            "AR": "▶ <b>تم استئناف الحساب</b>\n\nالمحرك شغال مرة أخرى.",
            "ES": "▶ <b>Cuenta reanudada</b>\n\nEl motor está funcionando de nuevo.",
        },
        "RESTARTED": {
            "EN": "🔄 <b>Engine Restarted</b>\n\nThe engine has been restarted.",
            "FR": "🔄 <b>Moteur redémarré</b>\n\nLe moteur a été redémarré.",
            "AR": "🔄 <b>تم إعادة تشغيل المحرك</b>\n\nتم إعادة تشغيل المحرك.",
            "ES": "🔄 <b>Motor reiniciado</b>\n\nEl motor ha sido reiniciado.",
        },
        "STARTED": {
            "EN": "▶ <b>Engine Started</b>\n\nThe engine is now running.",
            "FR": "▶ <b>Moteur démarré</b>\n\nLe moteur fonctionne maintenant.",
            "AR": "▶ <b>تم تشغيل المحرك</b>\n\nالمحرك شغال الآن.",
            "ES": "▶ <b>Motor iniciado</b>\n\nEl motor está funcionando ahora.",
        },
    }
    return msgs.get(key, {}).get(lang, msgs.get(key, {}).get("EN", key))

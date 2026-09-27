import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from telegram_bot.ui.callbacks import Callback

logger = logging.getLogger(__name__)

from telegram_bot.handlers.callbacks.language import handle_language
from telegram_bot.handlers.callbacks.account_type import handle_account_type
from telegram_bot.handlers.callbacks.broker import handle_broker
from telegram_bot.handlers.callbacks.trading_mode import handle_trading_mode
from telegram_bot.handlers.callbacks.prop_firm import handle_prop_firm
from telegram_bot.handlers.callbacks.funded_size import handle_funded_size
from telegram_bot.handlers.callbacks.challenge_type import handle_challenge_type
from telegram_bot.handlers.callbacks.back import handle_back
from telegram_bot.handlers.callbacks.mt5 import handle_mt5_continue
from telegram_bot.handlers.callbacks.terms import handle_terms_accept
from telegram_bot.handlers.callbacks.platform import handle_platform
from telegram_bot.handlers.callbacks.prop_program import handle_prop_program
from telegram_bot.handlers.callbacks.server import handle_server
from telegram_bot.handlers.callbacks.setup_confirm import handle_confirm_setup, handle_edit_setup
from telegram_bot.handlers.callbacks.activate_bot import handle_activate_bot
from telegram_bot.handlers.callbacks.enter_license_key import handle_enter_license_key
from telegram_bot.handlers.callbacks.connection_retry import handle_retry_connection, handle_restart_setup
from telegram_bot.handlers.callbacks.menu import handle_main_menu, handle_my_accounts, handle_active_accounts, handle_nav_back, handle_add_account, handle_change_language
from telegram_bot.handlers.callbacks.account_detail import handle_account_detail
from telegram_bot.handlers.callbacks.remove_account import handle_account_remove, handle_account_remove_confirm, handle_account_remove_cancel
from telegram_bot.handlers.callbacks.pause_resume import handle_account_pause, handle_account_resume, handle_account_restart, handle_account_start
from telegram_bot.handlers.callbacks.rescan_account import handle_account_rescan
from telegram_bot.handlers.callbacks.rename_account import handle_account_rename
from telegram_bot.handlers.callbacks.risk_mode import handle_risk_settings, handle_risk_mode_select, handle_risk_mode_confirm, handle_risk_mode_cancel
from telegram_bot.handlers.menu_pages import handle_system_status, handle_license_page, handle_performance_page, handle_support_page
from telegram_bot.handlers.start import start_handler
from database.db import async_session_factory
from database.repositories import UserRepository


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

    callback = query.data
    logger.info("Callback received: %s", callback)

    try:
        await _route_callback(update, context, callback)
    except BadRequest as e:
        if "Message is not modified" in str(e):
            return
        logger.warning("BadRequest for %s: %s", callback, e)
    except Exception as e:
        logger.exception("Callback handler error for %s: %s", callback, e)
        try:
            await query.edit_message_text(
                text=f"⚠️ <b>Error</b>\n\n<code>{e}</code>",
                parse_mode="HTML",
            )
        except Exception:
            pass


async def _handle_view_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE, key: str):
    """Send the full ICT analysis chart (all overlays) for a stored signal."""
    query = update.callback_query
    alert_service = context.bot_data.get("alert_service")
    if alert_service is None:
        await query.answer("Service unavailable. Please try again.", show_alert=True)
        return
    snapshot = alert_service.get_analysis_snapshot(key)
    if not snapshot:
        await query.answer("Analysis no longer available — request a new signal.", show_alert=True)
        return
    try:
        img = alert_service.renderer.render_snapshot(snapshot, minimal=False)
        image_bytes = alert_service.renderer.to_bytes(img)
    except Exception as e:
        logger.exception("Failed to render analysis chart for %s: %s", key, e)
        await query.answer("Could not render analysis.", show_alert=True)
        return
    await query.answer()
    caption = (
        "\U0001f50d <b>Full Analysis</b>\n"
        "<i>Complete ICT structure: BOS / CHoCH / MSS / OB / FVG / Liquidity</i>"
    )
    try:
        await query.message.reply_photo(
            photo=image_bytes, caption=caption, parse_mode="HTML",
        )
    except Exception as e:
        logger.warning("Failed to send analysis photo: %s", e)


async def _route_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, callback: str):
    # ---- Signal Analysis (View Analysis button) ----
    if callback.startswith("ANALYSIS:"):
        await _handle_view_analysis(update, context, callback.split(":", 1)[1])
        return

    # ---- Language ----
    if callback in [Callback.LANG_EN, Callback.LANG_FR, Callback.LANG_AR, Callback.LANG_ES]:
        if context.user_data.get("changing_language"):
            await _handle_language_menu_change(update, context, callback)
        else:
            await handle_language(update, context)
        return

    # ---- Main Menu Navigation ----
    if callback == Callback.MENU_MAIN:
        await handle_main_menu(update, context)
        return
    if callback == Callback.MENU_ACCOUNTS:
        await handle_my_accounts(update, context)
        return
    if callback == Callback.MENU_ACTIVE:
        await handle_active_accounts(update, context)
        return

    # ---- Ticket Flow ----
    if callback == Callback.TICKET_CREATE:
        from telegram_bot.handlers.menu_pages import handle_ticket_create
        await handle_ticket_create(update, context)
        return
    if callback.startswith("TICKET:CAT:"):
        from telegram_bot.handlers.menu_pages import handle_ticket_category
        category = callback.split(":", 2)[2]
        await handle_ticket_category(update, context, category)
        return
    if callback == Callback.TICKET_LIST:
        from telegram_bot.menus.support_menu import render_my_tickets
        await render_my_tickets(update, context)
        return
    if callback.startswith(Callback.TICKET_VIEW):
        from telegram_bot.menus.support_menu import render_ticket_detail
        ticket_id = callback[len(Callback.TICKET_VIEW):]
        await render_ticket_detail(update, context, ticket_id)
        return
    if callback.startswith(Callback.TICKET_REPLY):
        from telegram_bot.menus.support_menu import start_ticket_reply
        ticket_id = callback[len(Callback.TICKET_REPLY):]
        await start_ticket_reply(update, context, ticket_id)
        return
    if callback.startswith(Callback.TICKET_STATUS):
        from telegram_bot.menus.support_menu import handle_ticket_status_filter
        status = callback[len(Callback.TICKET_STATUS):]
        await handle_ticket_status_filter(update, context, status)
        return

    # ---- Menu Pages ----
    if callback == Callback.MENU_STATUS:
        await handle_system_status(update, context)
        return
    if callback == Callback.MENU_PERFORMANCE:
        await handle_performance_page(update, context)
        return
    if callback == Callback.MENU_LICENSE:
        await handle_license_page(update, context)
        return
    if callback == Callback.MENU_SUPPORT:
        await handle_support_page(update, context)
        return

    # ---- Navigation Back ----
    if callback == Callback.NAV_BACK:
        await handle_nav_back(update, context)
        return

    # ---- Account Actions (new format ACCOUNT:ACTION:ID) ----
    if callback.startswith("ACCOUNT:OPEN:"):
        await handle_account_detail(update, context)
        return
    if callback.startswith("ACCOUNT:PAUSE:"):
        await handle_account_pause(update, context)
        return
    if callback.startswith("ACCOUNT:RESUME:"):
        await handle_account_resume(update, context)
        return
    if callback.startswith("ACCOUNT:RESTART:"):
        await handle_account_restart(update, context)
        return
    if callback.startswith("ACCOUNT:RESCAN:"):
        await handle_account_rescan(update, context)
        return
    if callback.startswith("ACCOUNT:RENAME:"):
        await handle_account_rename(update, context)
        return
    if callback.startswith("ACCOUNT:REMOVE_CONFIRM:"):
        await handle_account_remove_confirm(update, context)
        return
    if callback.startswith("ACCOUNT:REMOVE_CANCEL:"):
        await handle_account_remove_cancel(update, context)
        return
    if callback.startswith("ACCOUNT:REMOVE:"):
        await handle_account_remove(update, context)
        return
    if callback.startswith("ACCOUNT:START:"):
        await handle_account_start(update, context)
        return
    if callback.startswith("SETTINGS:"):
        await handle_risk_settings(update, context)
        return

    # ---- Risk Mode ----
    if callback.startswith("RMS:"):
        await handle_risk_mode_select(update, context)
        return
    if callback.startswith("RMC:"):
        await handle_risk_mode_confirm(update, context)
        return
    if callback.startswith("RMX:"):
        await handle_risk_mode_cancel(update, context)
        return

    # ---- Legacy Account Callbacks (support old buttons still in chat) ----
    if callback == "MY_ACCOUNTS":
        await handle_my_accounts(update, context)
        return
    if callback.startswith("ACCOUNT_DETAIL:"):
        await handle_account_detail(update, context)
        return
    if callback.startswith("ACCOUNT_REMOVE_CONFIRM:"):
        await handle_account_remove_confirm(update, context)
        return
    if callback.startswith("ACCOUNT_REMOVE_CANCEL:"):
        await handle_account_remove_cancel(update, context)
        return
    if callback.startswith("ACCOUNT_REMOVE:"):
        await handle_account_remove(update, context)
        return
    if callback.startswith("ACCOUNT_START:"):
        await handle_account_start(update, context)
        return
    if callback.startswith("ACCOUNT_PAUSE:"):
        await handle_account_pause(update, context)
        return
    if callback.startswith("ACCOUNT_RESUME:"):
        await handle_account_resume(update, context)
        return
    if callback.startswith("ACCOUNT_RESTART:"):
        await handle_account_restart(update, context)
        return
    if callback.startswith("ACCOUNT_RESCAN:"):
        await handle_account_rescan(update, context)
        return
    if callback.startswith("ACCOUNT_RENAME:"):
        await handle_account_rename(update, context)
        return

    # ---- Add Account ----
    if callback == Callback.ADD_ACCOUNT:
        await handle_add_account(update, context)
        return

    # ---- Language Change ----
    if callback == Callback.MENU_LANGUAGE:
        await handle_change_language(update, context)
        return

    # ---- Dashboard ----
    if callback == Callback.MENU_DASHBOARD:
        await _placeholder_msg(update, "🌍 Dashboard")
        return

    # ---- Wizard Onboarding Callbacks ----
    if callback in [Callback.PERSONAL, Callback.FUNDED, Callback.CHALLENGE]:
        await handle_account_type(update, context)
        return
    if callback.startswith("BROKER:"):
        await handle_broker(update, context)
        return
    if callback.startswith("MODE:"):
        await handle_trading_mode(update, context)
        return
    if callback.startswith("PROP:"):
        await handle_prop_firm(update, context)
        return
    if callback.startswith("FUNDED_SIZE:"):
        await handle_funded_size(update, context)
        return
    if callback.startswith("CHALLENGE:"):
        await handle_challenge_type(update, context)
        return
    if callback.startswith("BACK_"):
        await handle_back(update, context)
        return
    if callback == "MT5_CONTINUE":
        await handle_mt5_continue(update, context)
        return
    if callback == "TERMS_ACCEPT":
        await handle_terms_accept(update, context)
        return
    if callback.startswith("PLATFORM:"):
        await handle_platform(update, context)
        return
    if callback.startswith("PROP_PROGRAM:"):
        await handle_prop_program(update, context)
        return
    if callback.startswith("SERVER:"):
        await handle_server(update, context)
        return

    # ---- Setup Confirm / Edit ----
    if callback == Callback.CONFIRM_SETUP:
        await handle_confirm_setup(update, context)
        return
    if callback == Callback.EDIT_SETUP:
        await handle_edit_setup(update, context)
        return

    # ---- Activation ----
    if callback == Callback.ACTIVATE_BOT:
        await handle_activate_bot(update, context)
        return
    if callback == Callback.ENTER_LICENSE_KEY:
        await handle_enter_license_key(update, context)
        return

    # ---- Connection Retry ----
    if callback == Callback.RETRY_CONNECTION:
        await handle_retry_connection(update, context)
        return
    if callback == Callback.RESTART_SETUP:
        await handle_restart_setup(update, context)
        return

    await update.callback_query.answer("Unknown action.", show_alert=True)


async def _placeholder_msg(update: Update, text: str):
    lang = (update.effective_user.language_code or "EN") if update.effective_user else "EN"
    await update.callback_query.edit_message_text(
        text=f"{text}\n\n{get_coming_soon(lang)}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(
                {"EN": "⬅️ Back", "FR": "⬅️ Retour", "AR": "⬅️ رجوع", "ES": "⬅️ Volver"}
                .get(lang, "⬅️ Back"),
                callback_data="NAV:BACK"
            )
        ]]),
    )


def get_coming_soon(lang: str) -> str:
    return {
        "EN": "This feature is under development.",
        "FR": "Cette fonctionnalité est en développement.",
        "AR": "هذه الميزة قيد التطوير.",
        "ES": "Esta función está en desarrollo.",
    }.get(lang, "This feature is under development.")


async def _handle_language_menu_change(update: Update, context: ContextTypes.DEFAULT_TYPE, callback: str):

    lang_map = {Callback.LANG_EN: "EN", Callback.LANG_FR: "FR", Callback.LANG_AR: "AR", Callback.LANG_ES: "ES"}
    new_lang = lang_map.get(callback, "EN")
    context.user_data["language"] = new_lang
    context.user_data.pop("changing_language", None)

    tg_user = update.effective_user
    async with async_session_factory() as session:
        repo = UserRepository(session)
        user = await repo.get_by_telegram_id(tg_user.id)
        if user:
            await repo.update_language(user.id, new_lang)
            await session.commit()

    await handle_main_menu(update, context)

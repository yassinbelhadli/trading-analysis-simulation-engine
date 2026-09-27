from telegram import Update
from telegram.ext import ContextTypes

from telegram_bot.ui.keyboards.servers import servers_keyboard
from telegram_bot.ui.keyboards.language import language_keyboard
from telegram_bot.services.setup import get_setup
from telegram_bot.data.prop_firms import get_prop_servers
from telegram_bot.data.brokers import get_broker_servers


RETRY_MESSAGES = {
    "EN": "🔄 <b>Retry Connection</b>\n\nChoose your server again:",
    "FR": "🔄 <b>Reconnexion</b>\n\nChoisissez à nouveau votre serveur :",
    "AR": "🔄 <b>إعادة الاتصال</b>\n\nاختر السيرفر مرة أخرى:",
    "ES": "🔄 <b>Reintentar conexión</b>\n\nElige tu servidor de nuevo:",
}


async def handle_retry_connection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    lang = context.user_data.get("language", "EN")
    setup = get_setup(context)

    # Clear old credentials
    setup["platform"]["server"] = None
    setup["platform"]["login"] = None
    setup["platform"]["password"] = None
    context.user_data.pop("mt_server", None)
    context.user_data.pop("mt_login", None)
    context.user_data.pop("mt_password", None)
    context.user_data.pop("encrypted_password", None)
    context.user_data["waiting_for"] = None

    # Try to get server list again
    servers = []
    account_type = context.user_data.get("account_type")
    platform = setup["platform"].get("type") or context.user_data.get("platform", "MT5")
    if account_type == "FUNDED":
        prop_id = context.user_data.get("prop_firm")
        servers = get_prop_servers(prop_id, platform)
    elif account_type == "PERSONAL":
        broker_id = context.user_data.get("broker")
        servers = get_broker_servers(broker_id, platform)

    if servers:
        await query.edit_message_text(
            text=RETRY_MESSAGES.get(lang, RETRY_MESSAGES["EN"]),
            parse_mode="HTML",
            reply_markup=servers_keyboard(servers),
        )
    else:
        context.user_data["waiting_for"] = "MT_SERVER"
        example = context.user_data.get("mt_server_example", "ICMarketsSC-MT5")
        retry_text = {
            "EN": f"🔄 <b>Server Name</b>\n\nType your server name again.\n\nExample:\n{example}",
            "FR": f"🔄 <b>Nom du serveur</b>\n\nTapez le nom du serveur à nouveau.\n\nExemple :\n{example}",
            "AR": f"🔄 <b>اسم السيرفر</b>\n\nاكتب اسم السيرفر مرة أخرى.\n\nمثال:\n{example}",
            "ES": f"🔄 <b>Nombre del servidor</b>\n\nEscribe el nombre del servidor de nuevo.\n\nEjemplo:\n{example}",
        }
        await query.edit_message_text(
            text=retry_text.get(lang, retry_text["EN"]),
            parse_mode="HTML",
        )


async def handle_restart_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    text = (
        "🚀 <b>ICT Funded EA Pro</b>\n\n"
        "Welcome!\n\n"
        "Please select your language:"
    )

    query = update.callback_query
    await query.edit_message_text(
        text=text,
        parse_mode="HTML",
        reply_markup=language_keyboard(),
    )

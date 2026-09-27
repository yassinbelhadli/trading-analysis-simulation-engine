from telegram import Update
from telegram.ext import ContextTypes

from telegram_bot.services.setup import get_setup


LOGIN_MESSAGES = {
    "EN": "🔢 <b>Login ID</b>\n\nPlease enter your account login number.\n\nExample:\n12345678",
    "FR": "🔢 <b>Login ID</b>\n\nVeuillez entrer le numéro de login du compte.\n\nExemple :\n12345678",
    "AR": "🔢 <b>رقم الدخول</b>\n\nاكتب رقم الدخول ديال الحساب.\n\nمثال:\n12345678",
    "ES": "🔢 <b>Login ID</b>\n\nEscribe el número de login de la cuenta.\n\nEjemplo:\n12345678",
}

SERVER_MESSAGES = {
    "EN": "🔐 <b>Server Name</b>\n\nType your server name manually.\n\nExample:\nICMarketsSC-MT5",
    "FR": "🔐 <b>Nom du serveur</b>\n\nTapez le nom du serveur manuellement.\n\nExemple :\nICMarketsSC-MT5",
    "AR": "🔐 <b>اسم السيرفر</b>\n\nاكتب اسم السيرفر يدوياً.\n\nمثال:\nICMarketsSC-MT5",
    "ES": "🔐 <b>Nombre del servidor</b>\n\nEscribe el nombre del servidor manualmente.\n\nEjemplo:\nICMarketsSC-MT5",
}


async def handle_server(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    server = query.data.replace("SERVER:", "")
    lang = context.user_data.get("language", "EN")
    setup = get_setup(context)

    if server == "OTHER":
        context.user_data["waiting_for"] = "MT_SERVER"
        await query.edit_message_text(
            text=SERVER_MESSAGES.get(lang, SERVER_MESSAGES["EN"]),
            parse_mode="HTML",
        )
        return

    setup["platform"]["server"] = server
    context.user_data["mt_server"] = server
    context.user_data["waiting_for"] = "MT_LOGIN"

    await query.edit_message_text(
        text=LOGIN_MESSAGES.get(lang, LOGIN_MESSAGES["EN"]),
        parse_mode="HTML",
    )
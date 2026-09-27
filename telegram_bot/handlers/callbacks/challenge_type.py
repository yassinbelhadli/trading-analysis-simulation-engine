from telegram import Update
from telegram.ext import ContextTypes

from telegram_bot.ui.keyboards.mt5 import mt5_warning_keyboard
from telegram_bot.services.setup import get_setup


CHALLENGE_MESSAGES = {
    "EN": {
        "title": "✅ <b>Challenge Type Selected</b>",
        "notice": "⚠️ <b>Security Notice</b>\n\nIf you don't trust the bot yet, connect a demo account first.",
    },
    "FR": {
        "title": "✅ <b>Type de challenge sélectionné</b>",
        "notice": "⚠️ <b>Avis de sécurité</b>\n\nSi vous ne faites pas encore confiance au bot, connectez d'abord un compte démo.",
    },
    "AR": {
        "title": "✅ <b>تم اختيار نوع التحدي</b>",
        "notice": "⚠️ <b>تنبيه أمني</b>\n\nإذا لم تكن واثقاً بالبوت بعد، يرجى ربط حساب تجريبي أولاً.",
    },
    "ES": {
        "title": "✅ <b>Tipo de challenge seleccionado</b>",
        "notice": "⚠️ <b>Aviso de seguridad</b>\n\nSi aún no confías en el bot, conecta primero una cuenta demo.",
    },
}


async def handle_challenge_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    challenge_type = query.data.replace("CHALLENGE:", "")

    setup = get_setup(context)
    setup["prop_firm"]["challenge_type"] = challenge_type

    context.user_data["challenge_type"] = challenge_type

    lang = context.user_data.get("language", "EN")
    t = CHALLENGE_MESSAGES.get(lang, CHALLENGE_MESSAGES["EN"])

    await query.edit_message_text(
        text=(
            f"{t['title']}\n\n"
            f"{challenge_type}\n\n"
            f"{t['notice']}"
        ),
        parse_mode="HTML",
        reply_markup=mt5_warning_keyboard(),
    )
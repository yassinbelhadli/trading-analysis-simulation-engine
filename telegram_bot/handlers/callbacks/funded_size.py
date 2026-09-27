from telegram import Update
from telegram.ext import ContextTypes

from telegram_bot.ui.keyboards.trading_modes import trading_modes_keyboard
from telegram_bot.services.setup import get_setup


FUNDED_SIZE_MESSAGES = {
    "EN": {
        "custom": "✍️ Type your account size. Example: 100K",
        "selected": "✅ <b>Account Size Selected</b>",
        "choose_mode": "⚙️ <b>Choose Trading Mode</b>",
    },
    "FR": {
        "custom": "✍️ Écrivez la taille du compte. Exemple: 100K",
        "selected": "✅ <b>Taille du compte sélectionnée</b>",
        "choose_mode": "⚙️ <b>Choisissez le mode de trading</b>",
    },
    "AR": {
        "custom": "✍️ اكتب حجم الحساب. مثال: 100K",
        "selected": "✅ <b>تم اختيار حجم الحساب</b>",
        "choose_mode": "⚙️ <b>اختر نمط التداول</b>",
    },
    "ES": {
        "custom": "✍️ Escribe el tamaño de la cuenta. Ejemplo: 100K",
        "selected": "✅ <b>Tamaño de cuenta seleccionado</b>",
        "choose_mode": "⚙️ <b>Elige el modo de trading</b>",
    },
}


async def handle_funded_size(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    size = query.data.replace("FUNDED_SIZE:", "")

    lang = context.user_data.get("language", "EN")
    t = FUNDED_SIZE_MESSAGES.get(lang, FUNDED_SIZE_MESSAGES["EN"])

    setup = get_setup(context)

    if size == "other":
        context.user_data["waiting_for"] = "CUSTOM_FUNDED_SIZE"
        await query.edit_message_text(t["custom"])
        return

    setup["account"]["balance"] = size
    setup["prop_firm"]["account_size"] = size

    context.user_data["funded_account_size"] = size

    await query.edit_message_text(
        text=(
            f"{t['selected']}\n\n"
            f"{size}\n\n"
            f"{t['choose_mode']}"
        ),
        parse_mode="HTML",
        reply_markup=trading_modes_keyboard(back_callback="BACK_PROP_FIRMS"),
    )
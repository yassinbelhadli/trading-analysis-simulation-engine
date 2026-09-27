from telegram import Update
from telegram.ext import ContextTypes

from telegram_bot.ui.keyboards.trading_modes import trading_modes_keyboard
from telegram_bot.services.navigation import push_page as set_page
from telegram_bot.services.setup import get_setup
from telegram_bot.data.brokers import get_broker


BROKER_MESSAGES = {
    "EN": {
        "selected": "✅ <b>Broker selected</b>",
        "choose_mode": "⚙️ <b>Choose Trading Mode</b>",
        "other": "✍️ Please enter your broker domain.\n\nExample:\nicmarkets.com\npepperstone.com",
    },
    "FR": {
        "selected": "✅ <b>Broker sélectionné</b>",
        "choose_mode": "⚙️ <b>Choisissez le mode de trading</b>",
        "other": "✍️ Entrez le domaine de votre broker.\n\nExemple :\nicmarkets.com\npepperstone.com",
    },
    "AR": {
        "selected": "✅ <b>تم اختيار الوسيط</b>",
        "choose_mode": "⚙️ <b>اختر نمط التداول</b>",
        "other": "✍️ اكتب نطاق (Domain) الوسيط.\n\nمثال:\nicmarkets.com\npepperstone.com",
    },
    "ES": {
        "selected": "✅ <b>Broker seleccionado</b>",
        "choose_mode": "⚙️ <b>Elige el modo de trading</b>",
        "other": "✍️ Ingresa el dominio de tu broker.\n\nEjemplo:\nicmarkets.com\npepperstone.com",
    },
}


async def handle_broker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    callback = query.data

    setup = get_setup(context)
    set_page(context, "BROKER")

    lang = context.user_data.get("language", "EN")
    t = BROKER_MESSAGES.get(lang, BROKER_MESSAGES["EN"])

    broker_id = callback.replace("BROKER:", "")

    if broker_id == "other":
        context.user_data["waiting_for"] = "CUSTOM_BROKER"
        setup["broker"]["id"] = "other"

        await query.edit_message_text(
            text=t["other"],
            parse_mode="HTML",
        )
        return

    broker = get_broker(broker_id)
    broker_name = broker["name"] if broker else broker_id

    setup["broker"]["id"] = broker_id
    setup["broker"]["name"] = broker_name

    context.user_data["broker"] = broker_id

    await query.edit_message_text(
        text=(
            f"{t['selected']}\n\n"
            f"{broker_name}\n\n"
            f"{t['choose_mode']}"
        ),
        parse_mode="HTML",
        reply_markup=trading_modes_keyboard(back_callback="BACK_BROKERS"),
    )
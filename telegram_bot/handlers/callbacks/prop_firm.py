from telegram import Update
from telegram.ext import ContextTypes

from telegram_bot.data.prop_firms import (
    get_prop_firm,
    get_prop_programs,
)
from telegram_bot.ui.keyboards.prop_programs import prop_programs_keyboard
from telegram_bot.services.navigation import push_page as set_page
from telegram_bot.services.setup import get_setup


PROP_MESSAGES = {
    "EN": {
        "other": "✍️ Please enter your prop firm domain.\n\nExample:\nftmo.com\nfundednext.com",
        "selected": "🏆 <b>Prop Firm Selected</b>",
        "choose_program": "📋 <b>Choose your Program</b>",
    },
    "FR": {
        "other": "✍️ Entrez le domaine de votre prop firm.\n\nExemple :\nftmo.com\nfundednext.com",
        "selected": "🏆 <b>Prop firm sélectionnée</b>",
        "choose_program": "📋 <b>Choisissez votre programme</b>",
    },
    "AR": {
        "other": "✍️ اكتب نطاق (Domain) شركة التمويل.\n\nمثال:\nftmo.com\nfundednext.com",
        "selected": "🏆 <b>تم اختيار شركة التمويل</b>",
        "choose_program": "📋 <b>اختر البرنامج</b>",
    },
    "ES": {
        "other": "✍️ Ingresa el dominio de tu prop firm.\n\nEjemplo:\nftmo.com\nfundednext.com",
        "selected": "🏆 <b>Prop firm seleccionada</b>",
        "choose_program": "📋 <b>Elige el programa</b>",
    },
}


async def handle_prop_firm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    prop_id = query.data.replace("PROP:", "")

    setup = get_setup(context)
    set_page(context, "PROP_FIRM")

    lang = context.user_data.get("language", "EN")
    t = PROP_MESSAGES.get(lang, PROP_MESSAGES["EN"])

    if prop_id == "other":
        setup["prop_firm"]["id"] = "other"
        context.user_data["waiting_for"] = "CUSTOM_PROP_FIRM"

        await query.edit_message_text(
            text=t["other"],
            parse_mode="HTML",
        )
        return

    firm = get_prop_firm(prop_id)

    if firm is None:
        await query.edit_message_text("❌ Invalid prop firm.")
        return

    setup["prop_firm"]["id"] = prop_id
    setup["prop_firm"]["name"] = firm["name"]

    context.user_data["prop_firm"] = prop_id
    context.user_data["prop_firm_name"] = firm["name"]

    programs = get_prop_programs(prop_id)

    await query.edit_message_text(
        text=(
            f"{t['selected']}\n\n"
            f"{firm['name']}\n\n"
            f"{t['choose_program']}"
        ),
        parse_mode="HTML",
        reply_markup=prop_programs_keyboard(programs),
    )
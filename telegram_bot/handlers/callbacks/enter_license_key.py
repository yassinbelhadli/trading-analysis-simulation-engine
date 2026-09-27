from telegram import Update
from telegram.ext import ContextTypes


async def handle_enter_license_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    lang = context.user_data.get("language", "EN")

    context.user_data["waiting_for"] = "LICENSE_KEY"

    messages = {
        "EN": "🔑 <b>Enter License Key</b>\n\nPlease type your license key.\n\nExample:\nXXXX-XXXX-XXXX-XXXX",
        "FR": "🔑 <b>Saisir la clé de licence</b>\n\nVeuillez taper votre clé de licence.\n\nExemple :\nXXXX-XXXX-XXXX-XXXX",
        "AR": "🔑 <b>أدخل مفتاح الترخيص</b>\n\nاكتب مفتاح الترخيص ديالك.\n\nمثال:\nXXXX-XXXX-XXXX-XXXX",
        "ES": "🔑 <b>Ingresar clave de licencia</b>\n\nEscribe tu clave de licencia.\n\nEjemplo:\nXXXX-XXXX-XXXX-XXXX",
    }

    await query.edit_message_text(
        text=messages.get(lang, messages["EN"]),
        parse_mode="HTML",
    )

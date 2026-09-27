from telegram import Update
from telegram.ext import ContextTypes

from database.db import async_session_factory
from database.repositories import UserRepository
from telegram_bot.ui.callbacks import Callback
from telegram_bot.services.license_service import license_service
from telegram_bot.ui.keyboards.account_type import account_type_keyboard
from telegram_bot.ui.keyboards.license_keyboard import no_license_keyboard
from telegram_bot.services.setup import get_setup


NO_LICENSE_MESSAGES = {
    "EN": "❌ <b>No Active License</b>\n\n"
          "You need an active license to use the bot.\n\n"
          "Purchase one from the Dashboard or enter an existing license key.",
    "FR": "❌ <b>Aucune licence active</b>\n\n"
          "Vous avez besoin d'une licence active pour utiliser le bot.\n\n"
          "Achetez-en une depuis le tableau de bord ou entrez une clé existante.",
    "AR": "❌ <b>لا توجد رخصة نشطة</b>\n\n"
          "تحتاج إلى رخصة نشطة لاستخدام البوت.\n\n"
          "اشترِ واحدة من لوحة التحكم أو أدخل مفتاح ترخيص موجود.",
    "ES": "❌ <b>Sin licencia activa</b>\n\n"
          "Necesitas una licencia activa para usar el bot.\n\n"
          "Cómprala desde el panel o ingresa una clave existente.",
}

ACCOUNT_MESSAGES = {
    "EN": "✅ <b>License Verified</b>\n\nChoose your account type.",
    "FR": "✅ <b>Licence vérifiée</b>\n\nChoisissez le type de compte.",
    "AR": "✅ <b>تم التحقق من الترخيص</b>\n\nاختر نوع الحساب.",
    "ES": "✅ <b>Licencia verificada</b>\n\nSeleccione el tipo de cuenta.",
}


async def handle_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    callback = query.data

    language_map = {
        Callback.LANG_EN: "EN",
        Callback.LANG_FR: "FR",
        Callback.LANG_AR: "AR",
        Callback.LANG_ES: "ES",
    }

    lang = language_map.get(callback, "EN")
    setup = get_setup(context)

    setup["language"] = lang
    setup["preferences"]["language"] = lang
    context.user_data["language"] = lang

    async with async_session_factory() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_or_create_by_telegram(
            telegram_id=update.effective_user.id,
            telegram_username=update.effective_user.username,
            first_name=update.effective_user.first_name,
            last_name=update.effective_user.last_name,
            language=lang,
        )
        await session.commit()

        result = await license_service.check(session, user.id, telegram_id=update.effective_user.id)

        if not result.valid:
            await query.edit_message_text(
                text=NO_LICENSE_MESSAGES[lang],
                parse_mode="HTML",
                reply_markup=no_license_keyboard(lang),
            )
            return

    await query.edit_message_text(
        text=ACCOUNT_MESSAGES[lang],
        parse_mode="HTML",
        reply_markup=account_type_keyboard(lang),
    )
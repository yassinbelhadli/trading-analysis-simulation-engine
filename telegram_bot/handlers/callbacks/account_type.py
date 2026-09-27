from telegram import Update
from telegram.ext import ContextTypes

from telegram_bot.ui.callbacks import Callback
from telegram_bot.ui.keyboards.brokers import brokers_keyboard
from telegram_bot.ui.keyboards.prop_firms import prop_firms_keyboard
from telegram_bot.services.navigation import push_page as set_page
from telegram_bot.services.setup import get_setup


ACCOUNT_TYPE_MESSAGES = {
    "EN": {
        "personal": "👤 <b>Personal Account selected.</b>\n\n🏦 Choose your broker:",
        "challenge": "🏋️ <b>Prop Firm Challenge selected.</b>\n\nChoose your prop firm:",
        "funded": "🏆 <b>Funded Account selected.</b>\n\nChoose your prop firm:",
    },
    "FR": {
        "personal": "👤 <b>Compte personnel sélectionné.</b>\n\n🏦 Choisissez votre broker :",
        "challenge": "🏋️ <b>Défi Prop Firm sélectionné.</b>\n\nChoisissez votre prop firm :",
        "funded": "🏆 <b>Compte funded sélectionné.</b>\n\nChoisissez votre prop firm :",
    },
    "AR": {
        "personal": "👤 <b>تم اختيار الحساب الشخصي.</b>\n\n🏦 اختر الوسيط الخاص بك:",
        "challenge": "🏋️ <b>تم اختيار تحدٍ لشركة تمويل.</b>\n\nاختر شركة التمويل:",
        "funded": "🏆 <b>تم اختيار الحساب الممول.</b>\n\nاختر شركة التمويل:",
    },
    "ES": {
        "personal": "👤 <b>Cuenta personal seleccionada.</b>\n\n🏦 Elige tu broker:",
        "challenge": "🏋️ <b>Desafío Prop Firm seleccionado.</b>\n\nElige tu prop firm:",
        "funded": "🏆 <b>Cuenta fondeada seleccionada.</b>\n\nElige tu prop firm:",
    },
}


async def handle_account_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    callback = query.data
    lang = context.user_data.get("language", "EN")

    setup = get_setup(context)
    set_page(context, "ACCOUNT_TYPE")

    if callback == Callback.PERSONAL:
        setup["account"]["type"] = "PERSONAL"
        context.user_data["account_type"] = "PERSONAL"

        await query.edit_message_text(
            text=ACCOUNT_TYPE_MESSAGES[lang]["personal"],
            parse_mode="HTML",
            reply_markup=brokers_keyboard(),
        )
        return

    if callback == Callback.FUNDED:
        setup["account"]["type"] = "FUNDED"
        context.user_data["account_type"] = "FUNDED"
        await query.edit_message_text(
            text=ACCOUNT_TYPE_MESSAGES[lang]["funded"],
            parse_mode="HTML",
            reply_markup=prop_firms_keyboard(),
        )
        return

    if callback == Callback.CHALLENGE:
        setup["account"]["type"] = "CHALLENGE"
        context.user_data["account_type"] = "CHALLENGE"
        await query.edit_message_text(
            text=ACCOUNT_TYPE_MESSAGES[lang]["challenge"],
            parse_mode="HTML",
            reply_markup=prop_firms_keyboard(),
        )
        return
from telegram import Update
from telegram.ext import ContextTypes

from telegram_bot.data.trading_modes import TRADING_MODES
from telegram_bot.locales.translator import tr
from telegram_bot.ui.keyboards.account_type import account_type_keyboard
from telegram_bot.ui.keyboards.brokers import brokers_keyboard
from telegram_bot.ui.keyboards.mt5 import mt5_warning_keyboard
from telegram_bot.ui.keyboards.platform import platform_keyboard
from telegram_bot.ui.keyboards.prop_firms import prop_firms_keyboard
from telegram_bot.ui.keyboards.terms import terms_keyboard
from telegram_bot.ui.keyboards.trading_modes import trading_modes_keyboard


BACK_MESSAGES = {
    "EN": {
        "account": "Choose your account type:",
        "broker": "🏦 Choose your broker:",
        "prop": "🏆 Choose your prop firm:",
    },
    "FR": {
        "account": "Choisissez votre type de compte :",
        "broker": "🏦 Choisissez votre broker :",
        "prop": "🏆 Choisissez votre prop firm :",
    },
    "AR": {
        "account": "اختر نوع الحساب:",
        "broker": "🏦 اختر الوسيط:",
        "prop": "🏆 اختر شركة التمويل:",
    },
    "ES": {
        "account": "Elige el tipo de cuenta:",
        "broker": "🏦 Elige tu broker:",
        "prop": "🏆 Elige tu prop firm:",
    },
}


TRADING_MODE_MESSAGES = {
    "EN": {"selected": "✅ <b>Trading Mode Selected</b>", "risk": "Risk"},
    "FR": {"selected": "✅ <b>Mode de trading sélectionné</b>", "risk": "Risque"},
    "AR": {"selected": "✅ <b>تم اختيار نمط التداول</b>", "risk": "المخاطرة"},
    "ES": {"selected": "✅ <b>Modo de trading seleccionado</b>", "risk": "Riesgo"},
}


def _find_mode(mode_id: str):
    for mode in TRADING_MODES:
        if mode["id"] == mode_id:
            return mode
    return None


async def handle_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    callback = query.data

    lang = context.user_data.get("language", "EN")
    t = BACK_MESSAGES.get(lang, BACK_MESSAGES["EN"])

    context.user_data["waiting_for"] = None

    if callback == "BACK_ACCOUNT_TYPE":
        await query.edit_message_text(
            text=t["account"],
            reply_markup=account_type_keyboard(),
        )
        return

    if callback == "BACK_BROKERS":
        await query.edit_message_text(
            text=t["broker"],
            reply_markup=brokers_keyboard(),
        )
        return

    if callback == "BACK_PROP_FIRMS":
        await query.edit_message_text(
            text=t["prop"],
            reply_markup=prop_firms_keyboard(),
        )
        return

    if callback == "BACK_TO_MODE":
        account_type = context.user_data.get("account_type")
        back_callback = "BACK_PROP_FIRMS" if account_type == "FUNDED" else "BACK_BROKERS"
        await query.edit_message_text(
            text="⚙️ <b>Choose Trading Mode</b>",
            parse_mode="HTML",
            reply_markup=trading_modes_keyboard(back_callback=back_callback),
        )
        return

    if callback == "BACK_MT_WARNING":
        mode_id = context.user_data.get("trading_mode")
        mode = _find_mode(mode_id)
        mt = TRADING_MODE_MESSAGES.get(lang, TRADING_MODE_MESSAGES["EN"])

        if mode:
            text = (
                f"{mt['selected']}\n\n"
                f"{mode['title']}\n\n"
                f"{mode['description']}\n\n"
                f"<b>{mt['risk']}:</b> {mode['risk']}\n\n"
                "⚠️ <b>Security Notice</b>\n\n"
                "If you don't trust the bot yet, connect a demo account first."
            )
        else:
            text = "⚠️ <b>Security Notice</b>\n\nIf you don't trust the bot yet, connect a demo account first."

        await query.edit_message_text(
            text=text,
            parse_mode="HTML",
            reply_markup=mt5_warning_keyboard(),
        )
        return

    if callback == "BACK_TERMS":
        await query.edit_message_text(
            text=(
                f"{tr(context, 'terms_title')}\n\n"
                f"{tr(context, 'terms_body')}"
            ),
            parse_mode="HTML",
            reply_markup=terms_keyboard(),
        )
        return

    if callback == "BACK_PLATFORM":
        await query.edit_message_text(
            text=(
                "🖥️ <b>Select your trading platform</b>\n\n"
                "Choose the platform used by your account."
            ),
            parse_mode="HTML",
            reply_markup=platform_keyboard(),
        )
        return

    await query.answer()
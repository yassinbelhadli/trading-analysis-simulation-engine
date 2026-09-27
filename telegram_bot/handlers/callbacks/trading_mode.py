from telegram import Update
from telegram.ext import ContextTypes

from telegram_bot.data.trading_modes import TRADING_MODES
from telegram_bot.ui.keyboards.challenge_type import challenge_type_keyboard
from telegram_bot.ui.keyboards.mt5 import mt5_warning_keyboard
from telegram_bot.services.setup import get_setup


MODE_MESSAGES = {
    "EN": {"selected": "✅ <b>Trading Mode Selected</b>", "risk": "Risk", "balance": "💰 <b>Type your account balance.</b>\nExample: 1000", "challenge": "🏆 <b>Choose challenge type</b>"},
    "FR": {"selected": "✅ <b>Mode de trading sélectionné</b>", "risk": "Risque", "balance": "💰 <b>Écrivez le solde du compte.</b>\nExemple: 1000", "challenge": "🏆 <b>Choisissez le type de challenge</b>"},
    "AR": {"selected": "✅ <b>تم اختيار نمط التداول</b>", "risk": "المخاطرة", "balance": "💰 <b>اكتب رصيد الحساب.</b>\nمثال: 1000", "challenge": "🏆 <b>اختر نوع التحدي</b>"},
    "ES": {"selected": "✅ <b>Modo de trading seleccionado</b>", "risk": "Riesgo", "balance": "💰 <b>Escribe el saldo de la cuenta.</b>\nEjemplo: 1000", "challenge": "🏆 <b>Elige el tipo de challenge</b>"},
}


def _find_mode(mode_id: str):
    for mode in TRADING_MODES:
        if mode["id"] == mode_id:
            return mode
    return None


async def handle_trading_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    mode_id = query.data.replace("MODE:", "")
    mode = _find_mode(mode_id)

    if mode is None:
        await query.edit_message_text("❌ Invalid trading mode.")
        return

    setup = get_setup(context)
    setup["trading"]["mode"] = mode_id
    context.user_data["trading_mode"] = mode_id

    lang = context.user_data.get("language", "EN")
    t = MODE_MESSAGES.get(lang, MODE_MESSAGES["EN"])

    account_type = setup["account"]["type"] or context.user_data.get("account_type")

    if account_type == "FUNDED":
        prop_id = setup["prop_firm"]["id"] or context.user_data.get("prop_firm")

        if prop_id != "other":
            await query.edit_message_text(
                text=(
                    f"{t['selected']}\n\n"
                    f"{mode['title']}\n\n"
                    f"{mode['description']}\n\n"
                    f"<b>{t['risk']}:</b> {mode['risk']}\n\n"
                    "⚠️ <b>Security Notice</b>\n\n"
                    "If you don't trust the bot yet, connect a demo account first."
                ),
                parse_mode="HTML",
                reply_markup=mt5_warning_keyboard(),
            )
            return

        await query.edit_message_text(
            text=(
                f"{t['selected']}\n\n"
                f"{mode['title']}\n\n"
                f"{mode['description']}\n\n"
                f"<b>{t['risk']}:</b> {mode['risk']}\n\n"
                f"{t['challenge']}"
            ),
            parse_mode="HTML",
            reply_markup=challenge_type_keyboard(["NO_CHALLENGE", "1_STEP", "2_STEP", "3_STEP"], lang),
        )
        return

    context.user_data["waiting_for"] = "ACCOUNT_BALANCE"

    await query.edit_message_text(
        text=(
            f"{t['selected']}\n\n"
            f"{mode['title']}\n\n"
            f"{mode['description']}\n\n"
            f"<b>{t['risk']}:</b> {mode['risk']}\n\n"
            f"{t['balance']}"
        ),
        parse_mode="HTML",
    )
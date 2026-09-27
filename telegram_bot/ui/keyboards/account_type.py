from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from telegram_bot.ui.callbacks import Callback


def account_type_keyboard(lang="EN"):
    texts = {
        "EN": {
            "personal": "👤 Personal Account",
            "challenge": "🏋️ Prop Firm Challenge",
            "funded": "🏆 Funded Account",
        },
        "FR": {
            "personal": "👤 Compte Personnel",
            "challenge": "🏋️ Défi Prop Firm",
            "funded": "🏆 Compte Funded",
        },
        "AR": {
            "personal": "👤 حساب شخصي",
            "challenge": "🏋️ تحدٍ لشركة تمويل",
            "funded": "🏆 حساب ممول",
        },
        "ES": {
            "personal": "👤 Cuenta Personal",
            "challenge": "🏋️ Desafío Prop Firm",
            "funded": "🏆 Cuenta Fondeada",
        },
    }

    t = texts.get(lang, texts["EN"])

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t["personal"], callback_data=Callback.PERSONAL)],
        [InlineKeyboardButton(t["challenge"], callback_data=Callback.CHALLENGE)],
        [InlineKeyboardButton(t["funded"], callback_data=Callback.FUNDED)],
    ])
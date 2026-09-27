from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def terms_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🛡️ Continue Secure Setup",
                callback_data="TERMS_ACCEPT"
            )
        ],
        [
            InlineKeyboardButton(
                "⬅️ Back",
                callback_data="BACK_MT_WARNING"
            )
        ],
    ])
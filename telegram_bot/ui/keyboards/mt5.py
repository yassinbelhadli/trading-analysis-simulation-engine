from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def mt5_warning_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Continue", callback_data="MT5_CONTINUE")
        ],
        [
            InlineKeyboardButton("⬅️ Back", callback_data="BACK_TO_MODE")
        ],
    ])
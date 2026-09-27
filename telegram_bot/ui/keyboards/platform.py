from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def platform_keyboard():
    """MT5-only: MT4 is no longer supported."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🟦 MetaTrader 5", callback_data="PLATFORM:MT5")
        ],
        [
            InlineKeyboardButton("⬅️ Back", callback_data="BACK_TERMS")
        ],
    ])
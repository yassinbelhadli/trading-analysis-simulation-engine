from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram_bot.data.prop_firms import PROP_FIRMS


def prop_firms_keyboard():
    keyboard = []

    for firm in PROP_FIRMS:
        keyboard.append([
            InlineKeyboardButton(
                firm["name"],
                callback_data=f"PROP:{firm['id']}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton("⬅️ Back", callback_data="BACK_ACCOUNT_TYPE")
    ])

    return InlineKeyboardMarkup(keyboard)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram_bot.data.brokers import BROKERS


def brokers_keyboard():
    keyboard = []

    for broker in BROKERS:
        keyboard.append([
            InlineKeyboardButton(
                broker["name"],
                callback_data=f"BROKER:{broker['id']}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton("⬅️ Back", callback_data="BACK_ACCOUNT_TYPE")
    ])

    return InlineKeyboardMarkup(keyboard)
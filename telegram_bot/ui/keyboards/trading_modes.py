from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram_bot.data.trading_modes import TRADING_MODES


def trading_modes_keyboard(back_callback="BACK_ACCOUNT_TYPE"):
    keyboard = []

    for mode in TRADING_MODES:
        keyboard.append([
            InlineKeyboardButton(
                f"{mode['title']} — Risk {mode['risk']}",
                callback_data=f"MODE:{mode['id']}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton("⬅️ Back", callback_data=back_callback)
    ])

    return InlineKeyboardMarkup(keyboard)
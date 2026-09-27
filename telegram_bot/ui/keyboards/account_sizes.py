from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def account_sizes_keyboard(sizes):
    keyboard = []

    for size in sizes:
        keyboard.append([
            InlineKeyboardButton(
                size,
                callback_data=f"FUNDED_SIZE:{size}",
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            "Other",
            callback_data="FUNDED_SIZE:other",
        )
    ])

    return InlineKeyboardMarkup(keyboard)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def servers_keyboard(servers):
    keyboard = []

    for server in servers:
        keyboard.append([
            InlineKeyboardButton(
                server,
                callback_data=f"SERVER:{server}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton("🖊 Other", callback_data="SERVER:OTHER")
    ])
    keyboard.append([
        InlineKeyboardButton("⬅️ Back", callback_data="BACK_PLATFORM")
    ])

    return InlineKeyboardMarkup(keyboard)
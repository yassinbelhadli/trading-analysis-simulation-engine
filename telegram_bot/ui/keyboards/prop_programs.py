from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def prop_programs_keyboard(programs):
    keyboard = []

    for program in programs:
        keyboard.append([
            InlineKeyboardButton(
                program["name"],
                callback_data=f"PROP_PROGRAM:{program['id']}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton("⬅️ Back", callback_data="BACK_PROP_FIRMS")
    ])

    return InlineKeyboardMarkup(keyboard)
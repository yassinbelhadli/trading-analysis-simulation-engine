from telegram import InlineKeyboardButton, InlineKeyboardMarkup


LABELS = {
    "EN": {
        "NO_CHALLENGE": "🚀 No Challenge / Instant",
        "1_STEP": "1️⃣ One Step",
        "2_STEP": "2️⃣ Two Step",
        "3_STEP": "3️⃣ Three Step",
        "back": "⬅️ Back",
    },
    "FR": {
        "NO_CHALLENGE": "🚀 Sans challenge / Instant",
        "1_STEP": "1️⃣ Une étape",
        "2_STEP": "2️⃣ Deux étapes",
        "3_STEP": "3️⃣ Trois étapes",
        "back": "⬅️ Retour",
    },
    "AR": {
        "NO_CHALLENGE": "🚀 بدون تحدي / مباشر",
        "1_STEP": "1️⃣ مرحلة واحدة",
        "2_STEP": "2️⃣ مرحلتين",
        "3_STEP": "3️⃣ ثلاث مراحل",
        "back": "⬅️ رجوع",
    },
    "ES": {
        "NO_CHALLENGE": "🚀 Sin reto / Instantáneo",
        "1_STEP": "1️⃣ Un paso",
        "2_STEP": "2️⃣ Dos pasos",
        "3_STEP": "3️⃣ Tres pasos",
        "back": "⬅️ Atrás",
    },
}


def challenge_type_keyboard(types, lang="EN"):
    labels = LABELS.get(lang, LABELS["EN"])

    keyboard = []

    for t in types:
        keyboard.append([
            InlineKeyboardButton(
                labels.get(t, t),
                callback_data=f"CHALLENGE:{t}",
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            labels["back"],
            callback_data="BACK_TO_MODE"
        )
    ])

    return InlineKeyboardMarkup(keyboard)
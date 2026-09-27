from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def activation_keyboard(lang: str = "EN"):
    labels = {
        "EN": "🚀 Activate Bot",
        "FR": "🚀 Activer le Bot",
        "AR": "🚀 تشغيل البوت",
        "ES": "🚀 Activar Bot",
    }
    home_labels = {
        "EN": "🏠 Main Menu",
        "FR": "🏠 Menu Principal",
        "AR": "🏠 القائمة الرئيسية",
        "ES": "🏠 Menú Principal",
    }
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(labels.get(lang, labels["EN"]), callback_data="ACTIVATE_BOT")],
        [InlineKeyboardButton(home_labels.get(lang, home_labels["EN"]), callback_data="MENU:MAIN")],
    ])

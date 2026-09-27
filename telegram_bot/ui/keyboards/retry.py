from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def retry_keyboard(lang: str = "EN"):
    labels = {
        "EN": {"retry": "🔄 Retry", "restart": "🏠 Restart"},
        "FR": {"retry": "🔄 Réessayer", "restart": "🏠 Redémarrer"},
        "AR": {"retry": "🔄 إعادة المحاولة", "restart": "🏠 البداية"},
        "ES": {"retry": "🔄 Reintentar", "restart": "🏠 Reiniciar"},
    }
    t = labels.get(lang, labels["EN"])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t["retry"], callback_data="RETRY_CONNECTION")],
        [InlineKeyboardButton(t["restart"], callback_data="RESTART_SETUP")],
    ])

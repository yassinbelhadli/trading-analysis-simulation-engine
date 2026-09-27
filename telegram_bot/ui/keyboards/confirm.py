from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def confirm_keyboard(lang: str = "EN"):
    labels = {
        "EN": {"confirm": "✅ Confirm", "edit": "✏ Edit Setup"},
        "FR": {"confirm": "✅ Confirmer", "edit": "✏ Modifier"},
        "AR": {"confirm": "✅ تأكيد", "edit": "✏ تعديل الإعداد"},
        "ES": {"confirm": "✅ Confirmar", "edit": "✏ Editar"},
    }
    t = labels.get(lang, labels["EN"])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t["confirm"], callback_data="CONFIRM_SETUP")],
        [InlineKeyboardButton(t["edit"], callback_data="EDIT_SETUP")],
    ])

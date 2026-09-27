from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from telegram_bot.ui.callbacks import Callback


def language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🇺🇸 English", callback_data=Callback.LANG_EN),
            InlineKeyboardButton("🇫🇷 Français", callback_data=Callback.LANG_FR),
        ],
        [
            InlineKeyboardButton("🇲🇦 العربية", callback_data=Callback.LANG_AR),
            InlineKeyboardButton("🇪🇸 Español", callback_data=Callback.LANG_ES),
        ],
    ])
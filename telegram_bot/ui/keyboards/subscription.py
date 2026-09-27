from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from telegram_bot.ui.callbacks import Callback


def subscription_keyboard(lang: str = "EN"):
    labels = {
        "EN": {
            "subscribe": "💳 Subscribe",
            "support": "💬 Contact Support",
        },
        "FR": {
            "subscribe": "💳 S’abonner",
            "support": "💬 Contacter le support",
        },
        "AR": {
            "subscribe": "💳 اشترك الآن",
            "support": "💬 تواصل مع الدعم",
        },
        "ES": {
            "subscribe": "💳 Suscribirse",
            "support": "💬 Contactar soporte",
        },
    }

    t = labels.get(lang, labels["EN"])

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    t["subscribe"],
                    url="https://ictfundedeapro.com/pricing",
                )
            ],
            [
                InlineKeyboardButton(
                    t["support"],
                    callback_data=Callback.MENU_SUPPORT,
                )
            ],
        ]
    )
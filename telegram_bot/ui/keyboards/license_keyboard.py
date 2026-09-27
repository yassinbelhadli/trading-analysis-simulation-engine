from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def no_license_keyboard(lang: str = "EN"):
    labels = {
        "EN": {
            "buy": "🌐 Buy License",
            "enter": "🔑 Enter License Key",
            "support": "💬 Contact Support",
        },
        "FR": {
            "buy": "🌐 Acheter une licence",
            "enter": "🔑 Saisir la clé de licence",
            "support": "💬 Contacter le support",
        },
        "AR": {
            "buy": "🌐 شراء رخصة",
            "enter": "🔑 إدخال مفتاح الترخيص",
            "support": "💬 تواصل مع الدعم",
        },
        "ES": {
            "buy": "🌐 Comprar licencia",
            "enter": "🔑 Ingresar clave de licencia",
            "support": "💬 Contactar soporte",
        },
    }
    t = labels.get(lang, labels["EN"])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t["buy"], url="https://ictfundedeapro.com/pricing")],
        [InlineKeyboardButton(t["enter"], callback_data="ENTER_LICENSE_KEY")],
        [InlineKeyboardButton(t["support"], callback_data="MENU:SUPPORT")],
    ])

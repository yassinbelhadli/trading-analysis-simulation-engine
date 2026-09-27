from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_keyboard(lang: str = "EN"):
    labels = {
        "EN": {
            "accounts": "📂 My Accounts",
            "active": "🟢 Active Accounts",
            "add": "➕ Add Account",
            "status": "📊 System Status",
            "license": "🔑 License",
            "support": "💬 New Ticket",
            "language": "🌐 Language",
            "dashboard": "🌍 Dashboard",
        },
        "FR": {
            "accounts": "📂 Mes Comptes",
            "active": "🟢 Comptes Actifs",
            "add": "➕ Ajouter un Compte",
            "status": "📊 État du Système",
            "license": "🔑 Licence",
            "support": "💬 Nouveau Ticket",
            "language": "🌐 Langue",
            "dashboard": "🌍 Tableau de Bord",
        },
        "AR": {
            "accounts": "📂 حساباتي",
            "active": "🟢 الحسابات النشطة",
            "add": "➕ إضافة حساب",
            "status": "📊 حالة النظام",
            "license": "🔑 الرخصة",
            "support": "💬 تذكرة جديدة",
            "language": "🌐 اللغة",
            "dashboard": "🌍 لوحة القيادة",
        },
        "ES": {
            "accounts": "📂 Mis Cuentas",
            "active": "🟢 Cuentas Activas",
            "add": "➕ Añadir Cuenta",
            "status": "📊 Estado del Sistema",
            "license": "🔑 Licencia",
            "support": "💬 Nuevo Ticket",
            "language": "🌐 Idioma",
            "dashboard": "🌍 Panel de Control",
        },
    }
    t = labels.get(lang, labels["EN"])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t["accounts"], callback_data="MENU:ACCOUNTS"),
         InlineKeyboardButton(t["active"], callback_data="MENU:ACTIVE")],
        [InlineKeyboardButton(t["add"], callback_data="ADD_ACCOUNT")],
        [InlineKeyboardButton(t["status"], callback_data="MENU:STATUS"),
         InlineKeyboardButton(t["license"], callback_data="MENU:LICENSE")],
        [InlineKeyboardButton(t["support"], callback_data="MENU:SUPPORT"),
         InlineKeyboardButton(t["language"], callback_data="MENU:LANGUAGE")],
    ])


def back_keyboard(lang: str = "EN"):
    label = {"EN": "⬅️ Back", "FR": "⬅️ Retour", "AR": "⬅️ رجوع", "ES": "⬅️ Volver"}
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label.get(lang, "⬅️ Back"), callback_data="NAV:BACK")],
    ])

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def accounts_list_keyboard(accounts: list, lang: str = "EN"):
    buttons = []
    for acc in accounts:
        label_parts = [acc.name or acc.server or acc.platform, f"#{acc.login}"]
        if acc.engine_status == "ACTIVE":
            label_parts.insert(0, "🟢")
        elif acc.engine_status == "PAUSED":
            label_parts.insert(0, "🟡")
        elif acc.engine_status in ("REMOVED", "DISABLED"):
            label_parts.insert(0, "🔴")
        else:
            label_parts.insert(0, "⚪")
        label = " ".join(label_parts)
        buttons.append([InlineKeyboardButton(label, callback_data=f"ACCOUNT:OPEN:{acc.id}")])

    buttons.append([InlineKeyboardButton(
        {"EN": "➕ Add Account", "FR": "➕ Ajouter un compte", "AR": "➕ إضافة حساب", "ES": "➕ Añadir cuenta"}.get(lang, "EN"),
        callback_data="ADD_ACCOUNT",
    )])
    buttons.append([InlineKeyboardButton(
        {"EN": "⬅️ Back", "FR": "⬅️ Retour", "AR": "⬅️ رجوع", "ES": "⬅️ Volver"}.get(lang, "⬅️ Back"),
        callback_data="NAV:BACK",
    )])
    return InlineKeyboardMarkup(buttons)


def account_detail_keyboard(account_id: str, engine_status: str, runtime_status: bool, lang: str = "EN"):
    labels = {
        "EN": {
            "start": "▶ Start Engine",
            "pause": "⏸ Pause",
            "restart": "🔄 Restart Engine",
            "resume": "▶ Resume",
            "rescan": "🔄 Rescan",
            "rename": "✏️ Rename",
            "settings": "⚙ Settings",
            "remove": "🗑 Remove",
            "back": "🔙 Back to Accounts",
        },
        "FR": {
            "start": "▶ Démarrer",
            "pause": "⏸ Pause",
            "restart": "🔄 Redémarrer",
            "resume": "▶ Reprendre",
            "rescan": "🔄 Re-scanner",
            "rename": "✏️ Renommer",
            "settings": "⚙ Paramètres",
            "remove": "🗑 Supprimer",
            "back": "🔙 Retour aux comptes",
        },
        "AR": {
            "start": "▶ تشغيل المحرك",
            "pause": "⏸ إيقاف مؤقت",
            "restart": "🔄 إعادة تشغيل",
            "resume": "▶ استئناف",
            "rescan": "🔄 إعادة فحص",
            "rename": "✏️ إعادة تسمية",
            "settings": "⚙ الإعدادات",
            "remove": "🗑 حذف",
            "back": "🔙 العودة للحسابات",
        },
        "ES": {
            "start": "▶ Iniciar Motor",
            "pause": "⏸ Pausar",
            "restart": "🔄 Reiniciar",
            "resume": "▶ Reanudar",
            "rescan": "🔄 Re-escanear",
            "rename": "✏️ Renombrar",
            "settings": "⚙ Ajustes",
            "remove": "🗑 Eliminar",
            "back": "🔙 Volver a cuentas",
        },
    }
    t = labels.get(lang, labels["EN"])
    buttons = []

    if engine_status == "ACTIVE":
        if runtime_status:
            buttons.append([InlineKeyboardButton(t["pause"], callback_data=f"ACCOUNT:PAUSE:{account_id}"),
                            InlineKeyboardButton(t["restart"], callback_data=f"ACCOUNT:RESTART:{account_id}")])
        else:
            buttons.append([InlineKeyboardButton(t["start"], callback_data=f"ACCOUNT:START:{account_id}")])
    elif engine_status in ("WAITING_ACTIVATION", "PAUSED", "SUSPENDED"):
        buttons.append([InlineKeyboardButton(t["resume"], callback_data=f"ACCOUNT:RESUME:{account_id}")])

    buttons.append([InlineKeyboardButton(t["rescan"], callback_data=f"ACCOUNT:RESCAN:{account_id}"),
                    InlineKeyboardButton(t["rename"], callback_data=f"ACCOUNT:RENAME:{account_id}")])
    buttons.append([InlineKeyboardButton(t["settings"], callback_data=f"SETTINGS:{account_id}"),
                    InlineKeyboardButton(t["remove"], callback_data=f"ACCOUNT:REMOVE:{account_id}")])
    buttons.append([InlineKeyboardButton(t["back"], callback_data="NAV:BACK")])
    return InlineKeyboardMarkup(buttons)


def account_remove_confirm_keyboard(account_id: str, lang: str = "EN"):
    labels = {
        "EN": ("🗑 Yes, Remove", "🔙 Cancel"),
        "FR": ("🗑 Oui, Supprimer", "🔙 Annuler"),
        "AR": ("🗑 نعم، احذف", "🔙 إلغاء"),
        "ES": ("🗑 Sí, Eliminar", "🔙 Cancelar"),
    }
    t = labels.get(lang, labels["EN"])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t[0], callback_data=f"ACCOUNT:REMOVE_CONFIRM:{account_id}")],
        [InlineKeyboardButton(t[1], callback_data=f"ACCOUNT:REMOVE_CANCEL:{account_id}")],
    ])

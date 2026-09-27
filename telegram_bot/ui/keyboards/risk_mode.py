from telegram import InlineKeyboardButton, InlineKeyboardMarkup

MODE_ICONS = {
    "ultra_conservative": "🛡️",
    "conservative": "🔵",
    "balanced": "🟡",
    "aggressive": "🔴",
}

MODE_LABELS = {
    "ultra_conservative": {
        "EN": "Ultra Conservative  (0.10%)",
        "FR": "Ultra Conservative  (0.10%)",
        "AR": "فائق الحذر  (0.10%)",
        "ES": "Ultra Conservador  (0.10%)",
    },
    "conservative": {
        "EN": "Conservative  (0.25%)",
        "FR": "Conservative  (0.25%)",
        "AR": "محافظ  (0.25%)",
        "ES": "Conservador  (0.25%)",
    },
    "balanced": {
        "EN": "Balanced  (0.50%)",
        "FR": "Équilibré  (0.50%)",
        "AR": "متوازن  (0.50%)",
        "ES": "Equilibrado  (0.50%)",
    },
    "aggressive": {
        "EN": "Aggressive  (1.00%)",
        "FR": "Agressif  (1.00%)",
        "AR": "هجومي  (1.00%)",
        "ES": "Agresivo  (1.00%)",
    },
}

_MODE_CODE = {"ultra_conservative": "u", "conservative": "c", "balanced": "b", "aggressive": "a"}
_MODES = ["ultra_conservative", "conservative", "balanced", "aggressive"]


def risk_mode_keyboard(account_id: str, current_mode: str, lang: str = "EN"):
    buttons = []
    for mode in _MODES:
        icon = MODE_ICONS[mode]
        label = MODE_LABELS[mode].get(lang, MODE_LABELS[mode]["EN"])
        prefix = "✅ " if mode == current_mode else ""
        buttons.append([InlineKeyboardButton(f"{prefix}{icon} {label}", callback_data=f"RMS:{account_id}:{_MODE_CODE[mode]}")])
    cancel_label = {"EN": "❌ Cancel", "FR": "❌ Annuler", "AR": "❌ إلغاء", "ES": "❌ Cancelar"}.get(lang, "❌ Cancel")
    buttons.append([InlineKeyboardButton(cancel_label, callback_data=f"RMX:{account_id}")])
    return InlineKeyboardMarkup(buttons)


def risk_mode_select_keyboard(account_id: str, pending_mode: str, lang: str = "EN"):
    icon = MODE_ICONS[pending_mode]
    label = MODE_LABELS[pending_mode].get(lang, MODE_LABELS[pending_mode]["EN"])
    confirm_label = {"EN": f"✅ Change to {icon} {label}", "FR": f"✅ Changer à {icon} {label}", "AR": f"✅ تغيير إلى {icon} {label}", "ES": f"✅ Cambiar a {icon} {label}"}.get(lang)
    cancel_label = {"EN": "❌ Cancel", "FR": "❌ Annuler", "AR": "❌ إلغاء", "ES": "❌ Cancelar"}.get(lang, "❌ Cancel")
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(confirm_label, callback_data=f"RMC:{account_id}:{_MODE_CODE[pending_mode]}")],
        [InlineKeyboardButton(cancel_label, callback_data=f"RMX:{account_id}")],
    ])

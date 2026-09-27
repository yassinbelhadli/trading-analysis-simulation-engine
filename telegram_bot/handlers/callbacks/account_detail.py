from telegram import Update
from telegram.ext import ContextTypes

from database.db import async_session_factory
from database.repositories import AccountRepository, UserRepository
from database.models import RiskProfile
from telegram_bot.ui.keyboards.accounts import account_detail_keyboard
from telegram_bot.services.navigation import push_page, PAGE_ACCOUNT_DETAIL
from core_engine.engine_manager import engine_manager


async def handle_account_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    lang = context.user_data.get("language", "EN")
    tg_user = update.effective_user
    callback = query.data

    account_id = callback.rsplit(":", 1)[-1] if ":" in callback else ""

    push_page(context, PAGE_ACCOUNT_DETAIL)

    async with async_session_factory() as session:
        acc_repo = AccountRepository(session)
        account = await acc_repo.get_by_id(account_id)

        if not account:
            await query.edit_message_text(text=_msg(lang, "NOT_FOUND"))
            return

        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(tg_user.id)
        if not user or account.user_id != user.id:
            await query.edit_message_text(text=_msg(lang, "NOT_FOUND"))
            return

        runtime_status = engine_manager.is_running(account.id)

    def v(val, fallback="—"):
        return val if val else fallback

    header = account.name or f"{account.server or account.platform} #{account.login or ''}"

    # Account status icon/label
    acc_icon = "🟢" if account.engine_status == "ACTIVE" else "🟡" if account.engine_status == "PAUSED" else "🔴"
    acc_label = _status_label(account.engine_status, lang)

    # Engine status icon/label
    eng_icon = "🟢" if runtime_status else "🔴"
    eng_label = _engine_running_label(runtime_status, lang)

    lines = [
        f"📊 <b>{header}</b>",
        "",
        f"┌─── <b>{_l(lang, 'ACCOUNT_SECTION')}</b>",
        f"│ {_l(lang, 'BROKER')}  {v(account.broker)}",
        f"│ {_l(lang, 'SERVER')}  {v(account.server)}",
        f"│ {_l(lang, 'LOGIN')}  <code>{v(account.login)}</code>",
        f"│ {_l(lang, 'TYPE')}  {v(account.account_type)}",
    ]

    if account.prop_firm:
        lines.append(f"│ {_l(lang, 'PROP_FIRM')}  {account.prop_firm} {v(account.program, '')}")
    if account.account_size:
        lines.append(f"│ {_l(lang, 'SIZE')}  ${_fmt(account.account_size)}")

    lines += [
        f"├─── <b>{_l(lang, 'BALANCE_SECTION')}</b>",
        f"│ {_l(lang, 'BALANCE')}  ${v(_fmt(account.balance_snapshot))}",
        f"│ {_l(lang, 'EQUITY')}  ${v(_fmt(account.equity_snapshot))}",
        f"│ {_l(lang, 'LEVERAGE')}  {_lev(account.leverage)}",
        f"│ {_l(lang, 'MODE')}  {v(account.trade_mode, '—').capitalize()}",
        f"├─── <b>{_l(lang, 'ENGINE_SECTION')}</b>",
        f"│ {acc_icon} {_l(lang, 'ACCOUNT_STATUS')}  {acc_label}",
        f"│ {eng_icon} {_l(lang, 'ENGINE_STATUS')}  {eng_label}",
        f"│ {_l(lang, 'PLATFORM')}  {account.platform}",
        f"│ {_l(lang, 'CREATED')}  {account.created_at.strftime('%Y-%m-%d %H:%M') if account.created_at else '—'} UTC",
        f"└────────────────────",
    ]

    # Risk section
    risk: RiskProfile = account.risk_profile
    if risk:
        dl_pct = risk.current_daily_loss_pct or 0.0
        ml_pct = risk.current_max_loss_pct or 0.0
        dl_limit = risk.daily_loss or 3.0
        ml_limit = risk.max_loss or 10.0
        mode_label = _mode_label(risk.mode, lang)
        risk_pct = risk.max_risk_trade or {"ultra_conservative": 0.10, "conservative": 0.25, "balanced": 0.50, "aggressive": 1.0}.get(risk.mode or "balanced", 0.5)
        lines += [
            f"├─── <b>{_l(lang, 'RISK_SECTION')}</b>",
            f"│ {_l(lang, 'MODE_LABEL')}  {mode_label} ({risk_pct:.2f}%)",
            f"│ {_l(lang, 'DL_CURRENT')}  {dl_pct:.1f}%  ({_l(lang, 'LIMIT')} {dl_limit:.0f}%)",
            f"│ {_l(lang, 'ML_CURRENT')}  {ml_pct:.1f}%  ({_l(lang, 'LIMIT')} {ml_limit:.0f}%)",
            f"└────────────────────",
        ]

    if not runtime_status and account.engine_status == "ACTIVE":
        lines += [
            "",
            _msg(lang, "ENGINE_WARNING"),
        ]

    await query.edit_message_text(
        text="\n".join(lines),
        parse_mode="HTML",
        reply_markup=account_detail_keyboard(account.id, account.engine_status, runtime_status, lang),
    )


def _engine_running_label(running: bool, lang: str) -> str:
    labels = {
        True: {"EN": "Running", "FR": "En marche", "AR": "شغال", "ES": "Ejecutándose"},
        False: {"EN": "Stopped", "FR": "Arrêté", "AR": "متوقف", "ES": "Detenido"},
    }
    return labels.get(running, {}).get(lang, labels[running]["EN"])


def _fmt(val):
    if val is None:
        return "—"
    try:
        vv = float(val)
        if vv >= 1000000:
            return f"{vv/1000000:.2f}M"
        if vv >= 1000:
            return f"{vv/1000:.2f}K"
        return f"{vv:.2f}"
    except (ValueError, TypeError):
        return str(val)


def _status_label(status: str, lang: str) -> str:
    labels = {
        "WAITING_ACTIVATION": {"EN": "Waiting Activation", "FR": "En attente d'activation", "AR": "في انتظار التفعيل", "ES": "Esperando activación"},
        "ACTIVE": {"EN": "Active", "FR": "Actif", "AR": "نشط", "ES": "Activo"},
        "PAUSED": {"EN": "Paused", "FR": "En pause", "AR": "متوقف مؤقتاً", "ES": "Pausado"},
        "SUSPENDED": {"EN": "Suspended", "FR": "Suspendu", "AR": "موقوف", "ES": "Suspendido"},
        "DISABLED": {"EN": "Disabled", "FR": "Désactivé", "AR": "معطل", "ES": "Desactivado"},
        "REMOVED": {"EN": "Removed", "FR": "Supprimé", "AR": "محذوف", "ES": "Eliminado"},
        "STOPPED": {"EN": "Stopped", "FR": "Arrêté", "AR": "متوقف", "ES": "Detenido"},
    }
    return labels.get(status, {}).get(lang, labels.get(status, {}).get("EN", status))


def _l(lang: str, key: str) -> str:
    labels = {
        "ACCOUNT_SECTION": {"EN": "Account", "FR": "Compte", "AR": "الحساب", "ES": "Cuenta"},
        "BALANCE_SECTION": {"EN": "Balance", "FR": "Solde", "AR": "الرصيد", "ES": "Balance"},
        "ENGINE_SECTION": {"EN": "Engine", "FR": "Moteur", "AR": "المحرك", "ES": "Motor"},
        "ACCOUNT_STATUS": {"EN": "Account", "FR": "Compte", "AR": "الحساب", "ES": "Cuenta"},
        "ENGINE_STATUS": {"EN": "Engine", "FR": "Moteur", "AR": "المحرك", "ES": "Motor"},
        "PLATFORM": {"EN": "Platform", "FR": "Plateforme", "AR": "المنصة", "ES": "Plataforma"},
        "SERVER": {"EN": "Server", "FR": "Serveur", "AR": "السيرفر", "ES": "Servidor"},
        "LOGIN": {"EN": "Login", "FR": "Login", "AR": "رقم الدخول", "ES": "Login"},
        "BROKER": {"EN": "Broker", "FR": "Broker", "AR": "الوسيط", "ES": "Broker"},
        "TYPE": {"EN": "Type", "FR": "Type", "AR": "النوع", "ES": "Tipo"},
        "BALANCE": {"EN": "Balance", "FR": "Solde", "AR": "الرصيد", "ES": "Balance"},
        "EQUITY": {"EN": "Equity", "FR": "Equité", "AR": "الحقوق", "ES": "Equidad"},
        "LEVERAGE": {"EN": "Leverage", "FR": "Levier", "AR": "الرافعة", "ES": "Apalancamiento"},
        "MODE": {"EN": "Mode", "FR": "Mode", "AR": "الوضع", "ES": "Modo"},
        "PROP_FIRM": {"EN": "Prop Firm", "FR": "Prop Firm", "AR": "شركة التمويل", "ES": "Prop Firm"},
        "SIZE": {"EN": "Account Size", "FR": "Taille du compte", "AR": "حجم الحساب", "ES": "Tamaño"},
        "CREATED": {"EN": "Created", "FR": "Créé", "AR": "تاريخ الإنشاء", "ES": "Creado"},
        "RISK_SECTION": {"EN": "Risk", "FR": "Risque", "AR": "المخاطرة", "ES": "Riesgo"},
        "DL_CURRENT": {"EN": "Daily Loss", "FR": "Perte journalière", "AR": "خسارة اليوم", "ES": "Pérdida diaria"},
        "ML_CURRENT": {"EN": "Max Loss", "FR": "Perte max", "AR": "أقصى خسارة", "ES": "Pérdida máxima"},
        "LIMIT": {"EN": "Limit", "FR": "Limite", "AR": "الحد", "ES": "Límite"},
        "MODE_LABEL": {"EN": "Mode", "FR": "Mode", "AR": "الوضع", "ES": "Modo"},
    }
    return labels.get(key, {}).get(lang, labels.get(key, {}).get("EN", key))


def _mode_label(mode: Optional[str], lang: str) -> str:
    labels = {
        "ultra_conservative": {"EN": "🛡️ Ultra Conservative", "FR": "🛡️ Ultra Conservative", "AR": "🛡️ فائق الحذر", "ES": "🛡️ Ultra Conservador"},
        "conservative": {"EN": "🔵 Conservative", "FR": "🔵 Conservative", "AR": "🔵 محافظ", "ES": "🔵 Conservador"},
        "balanced": {"EN": "🟡 Balanced", "FR": "🟡 Équilibré", "AR": "🟡 متوازن", "ES": "🟡 Equilibrado"},
        "aggressive": {"EN": "🔴 Aggressive", "FR": "🔴 Agressif", "AR": "🔴 هجومي", "ES": "🔴 Agresivo"},
    }
    return labels.get(mode or "balanced", {}).get(lang, labels.get(mode or "balanced", {}).get("EN", mode or "Balanced"))


def _lev(val):
    if not val:
        return "—"
    s = str(val).replace("1:", "")
    return f"1:{s}"


def _msg(lang: str, key: str) -> str:
    msgs = {
        "NOT_FOUND": {"EN": "❌ Account not found.", "FR": "❌ Compte introuvable.", "AR": "❌ الحساب غير موجود.", "ES": "❌ Cuenta no encontrada."},
        "ENGINE_WARNING": {
            "EN": (
                "⚠️ <b>Trading engine is not running.</b>\n\n"
                "The following will NOT work:\n"
                "• Market scanning\n"
                "• Trade signals\n"
                "• Strategy execution\n"
                "• Notifications\n\n"
                'Press "▶ Start Engine" or contact support.'
            ),
            "FR": (
                "⚠️ <b>Le moteur de trading ne fonctionne pas.</b>\n\n"
                "Les éléments suivants ne fonctionneront PAS :\n"
                "• Analyse du marché\n"
                "• Signaux de trading\n"
                "• Exécution de la stratégie\n"
                "• Notifications\n\n"
                'Appuyez sur "▶ Démarrer" ou contactez le support.'
            ),
            "AR": (
                "⚠️ <b>محرك التداول غير شغال حالياً.</b>\n\n"
                "لن يتم:\n"
                "• فحص السوق\n"
                "• إشارات التداول\n"
                "• تنفيذ الاستراتيجية\n"
                "• التنبيهات\n\n"
                'اضغط "▶ تشغيل المحرك" أو تواصل مع الدعم.'
            ),
            "ES": (
                "⚠️ <b>El motor de trading no está funcionando.</b>\n\n"
                "Lo siguiente NO funcionará:\n"
                "• Escaneo del mercado\n"
                "• Señales de trading\n"
                "• Ejecución de estrategias\n"
                "• Notificaciones\n\n"
                'Presione "▶ Iniciar Motor" o contacte al soporte.'
            ),
        },
    }
    return msgs.get(key, {}).get(lang, msgs.get(key, {}).get("EN", key))

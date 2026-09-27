import logging
from datetime import datetime, timezone

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from sqlalchemy import select, func

from database.db import async_session_factory
from database.repositories import UserRepository, LicenseRepository, AccountRepository
from database.models import SupportTicket
from telegram_bot.ui.icons import Icons

logger = logging.getLogger(__name__)


def _back_btn(lang: str = "EN") -> InlineKeyboardMarkup:
    label = {"EN": "⬅️ Back", "FR": "⬅️ Retour", "AR": "⬅️ رجوع", "ES": "⬅️ Volver"}
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label.get(lang, "⬅️ Back"), callback_data="NAV:BACK")]
    ])


def _msg(lang: str, d: dict) -> str:
    return d.get(lang, d["EN"])


async def handle_system_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    lang = context.user_data.get("language", "EN")

    text = _msg(lang, {
        "EN": (
            f"{Icons.BOT} <b>System Status</b>\n\n"
            f"{Icons.ONLINE} Bot: <b>Running</b>\n"
            f"{Icons.DASHBOARD} API: <b>Connected</b>\n"
            f"{Icons.CHECK} Database: <b>OK</b>\n\n"
            f"{Icons.INFO} Uptime monitoring active.\n"
            f"All systems operational."
        ),
        "AR": (
            f"{Icons.BOT} <b>حالة النظام</b>\n\n"
            f"{Icons.ONLINE} البوت: <b>يعمل</b>\n"
            f"{Icons.DASHBOARD} API: <b>متصل</b>\n"
            f"{Icons.CHECK} قاعدة البيانات: <b>سليمة</b>\n\n"
            f"{Icons.INFO} مراقبة مدة التشغيل نشطة.\n"
            f"جميع الأنظمة تعمل بشكل طبيعي."
        ),
        "FR": (
            f"{Icons.BOT} <b>État du Système</b>\n\n"
            f"{Icons.ONLINE} Bot: <b>En marche</b>\n"
            f"{Icons.DASHBOARD} API: <b>Connectée</b>\n"
            f"{Icons.CHECK} Base de données: <b>OK</b>\n\n"
            f"{Icons.INFO} Surveillance active.\n"
            f"Tous les systèmes opérationnels."
        ),
        "ES": (
            f"{Icons.BOT} <b>Estado del Sistema</b>\n\n"
            f"{Icons.ONLINE} Bot: <b>Ejecutándose</b>\n"
            f"{Icons.DASHBOARD} API: <b>Conectada</b>\n"
            f"{Icons.CHECK} Base de datos: <b>OK</b>\n\n"
            f"{Icons.INFO} Monitoreo activo.\n"
            f"Todos los sistemas operativos."
        ),
    })

    await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=_back_btn(lang))


async def handle_license_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    lang = context.user_data.get("language", "EN")
    tg_user = update.effective_user

    try:
        async with async_session_factory() as session:
            user_repo = UserRepository(session)
            lic_repo = LicenseRepository(session)
            user = await user_repo.get_by_telegram_id(tg_user.id)

            if user:
                licenses = await lic_repo.get_by_user_id(user.id)
                active = [l for l in licenses if l.status == "active"]
            else:
                licenses = []
                active = []

        if active:
            lic = active[0]
            plan = lic.plan or "N/A"
            key = lic.license_key or "N/A"
            expires = lic.expires_at.strftime("%Y-%m-%d") if lic.expires_at else "N/A"
            max_acc = lic.max_accounts or 1
            bound = len([l for l in licenses if l.bound_account_id is not None])

            text = _msg(lang, {
                "EN": (
                    f"{Icons.LICENSE} <b>License Info</b>\n\n"
                    f"Key: <code>{key}</code>\n"
                    f"Plan: <b>{plan}</b>\n"
                    f"Status: {Icons.ONLINE} <b>Active</b>\n"
                    f"Expires: {expires}\n"
                    f"Accounts: {bound}/{max_acc} bound\n\n"
                    f"{Icons.STAR} All systems active."
                ),
                "AR": (
                    f"{Icons.LICENSE} <b>معلومات الترخيص</b>\n\n"
                    f"المفتاح: <code>{key}</code>\n"
                    f"الباقة: <b>{plan}</b>\n"
                    f"الحالة: {Icons.ONLINE} <b>نشط</b>\n"
                    f"ينتهي: {expires}\n"
                    f"الحسابات: {bound}/{max_acc} مرتبطة\n\n"
                    f"{Icons.STAR} جميع الأنظمة نشطة."
                ),
                "FR": (
                    f"{Icons.LICENSE} <b>Informations de Licence</b>\n\n"
                    f"Clé: <code>{key}</code>\n"
                    f"Plan: <b>{plan}</b>\n"
                    f"Statut: {Icons.ONLINE} <b>Active</b>\n"
                    f"Expire: {expires}\n"
                    f"Comptes: {bound}/{max_acc} liés\n\n"
                    f"{Icons.STAR} Tous les systèmes actifs."
                ),
                "ES": (
                    f"{Icons.LICENSE} <b>Información de Licencia</b>\n\n"
                    f"Clave: <code>{key}</code>\n"
                    f"Plan: <b>{plan}</b>\n"
                    f"Estado: {Icons.ONLINE} <b>Activa</b>\n"
                    f"Expira: {expires}\n"
                    f"Cuentas: {bound}/{max_acc} vinculadas\n\n"
                    f"{Icons.STAR} Todos los sistemas activos."
                ),
            })
        else:
            text = _msg(lang, {
                "EN": f"{Icons.LICENSE} <b>License</b>\n\nNo active license found.\n\nVisit the dashboard to purchase or activate your license.",
                "AR": f"{Icons.LICENSE} <b>الرخصة</b>\n\nلا توجد رخصة نشطة.\n\nقم بزيارة لوحة التحكم لشراء أو تفعيل رخصتك.",
                "FR": f"{Icons.LICENSE} <b>Licence</b>\n\nAucune licence active.\n\nVisitez le tableau de bord pour acheter ou activer votre licence.",
                "ES": f"{Icons.LICENSE} <b>Licencia</b>\n\nNo hay licencia activa.\n\nVisita el panel para comprar o activar tu licencia.",
            })
    except Exception as e:
        logger.error("License page error: %s", e)
        text = _msg(lang, {
            "EN": f"{Icons.ERROR} Unable to load license info. Please try again.",
            "AR": f"{Icons.ERROR} تعذر تحميل معلومات الترخيص. حاول مرة أخرى.",
            "FR": f"{Icons.ERROR} Impossible de charger les infos de licence. Réessayez.",
            "ES": f"{Icons.ERROR} No se pudo cargar la licencia. Intenta de nuevo.",
        })

    await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=_back_btn(lang))


async def handle_performance_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    lang = context.user_data.get("language", "EN")
    tg_user = update.effective_user

    try:
        from sqlalchemy import inspect, select, func
        from database.models import Base

        async with async_session_factory() as session:
            user_repo = UserRepository(session)
            user = await user_repo.get_by_telegram_id(tg_user.id)
            trades_count = 0
            wins = 0
            total_pnl = 0.0

            if user:
                # Check if trades table exists
                inspector = await session.run_sync(lambda sync_sess: inspect(sync_sess).has_table("trades"))
                if inspector:
                    from database.models import Trade
                    result = await session.execute(
                        select(func.count(Trade.id), func.sum(Trade.realized_pnl))
                        .where(Trade.user_id == user.id)
                    )
                    row = result.one()
                    trades_count = row[0] or 0
                    total_pnl = float(row[1] or 0)

                    result2 = await session.execute(
                        select(func.count(Trade.id))
                        .where(Trade.user_id == user.id, Trade.realized_pnl > 0)
                    )
                    wins = result2.scalar() or 0
                total_pnl = total_pnl

        losses = trades_count - wins
        win_rate = round((wins / trades_count * 100), 1) if trades_count else 0
        pf = round(total_pnl / abs(total_pnl), 2) if total_pnl and abs(total_pnl) > 0 else 0.0

        text = _msg(lang, {
            "EN": (
                f"{Icons.DASHBOARD} <b>Performance Dashboard</b>\n\n"
                f"Total Trades: <b>{trades_count}</b>\n"
                f"{Icons.WIN} Wins: <b>{wins}</b>\n"
                f"{Icons.LOSS} Losses: <b>{losses}</b>\n"
                f"Win Rate: <b>{win_rate}%</b>\n"
                f"Net PnL: <b>${total_pnl:+,.2f}</b>\n"
                f"Profit Factor: <b>{pf:.2f}</b>\n\n"
                f"{Icons.CHART} Detailed stats coming soon."
            ),
            "AR": (
                f"{Icons.DASHBOARD} <b>لوحة الأداء</b>\n\n"
                f"إجمالي الصفقات: <b>{trades_count}</b>\n"
                f"{Icons.WIN} رابحة: <b>{wins}</b>\n"
                f"{Icons.LOSS} خاسرة: <b>{losses}</b>\n"
                f"نسبة الربح: <b>{win_rate}%</b>\n"
                f"صافي الربح: <b>${total_pnl:+,.2f}</b>\n"
                f"عامل الربح: <b>{pf:.2f}</b>\n\n"
                f"{Icons.CHART} إحصائيات مفصلة قريباً."
            ),
            "FR": (
                f"{Icons.DASHBOARD} <b>Tableau de Performance</b>\n\n"
                f"Total Transactions: <b>{trades_count}</b>\n"
                f"{Icons.WIN} Gains: <b>{wins}</b>\n"
                f"{Icons.LOSS} Pertes: <b>{losses}</b>\n"
                f"Taux de Réussite: <b>{win_rate}%</b>\n"
                f"PnL Net: <b>${total_pnl:+,.2f}</b>\n"
                f"Facteur de Profit: <b>{pf:.2f}</b>\n\n"
                f"{Icons.CHART} Stats détaillées à venir."
            ),
            "ES": (
                f"{Icons.DASHBOARD} <b>Panel de Rendimiento</b>\n\n"
                f"Total Operaciones: <b>{trades_count}</b>\n"
                f"{Icons.WIN} Ganancias: <b>{wins}</b>\n"
                f"{Icons.LOSS} Pérdidas: <b>{losses}</b>\n"
                f"Tasa de Éxito: <b>{win_rate}%</b>\n"
                f"PnL Neto: <b>${total_pnl:+,.2f}</b>\n"
                f"Factor de Beneficio: <b>{pf:.2f}</b>\n\n"
                f"{Icons.CHART} Estadísticas detalladas próximamente."
            ),
        })
    except Exception as e:
        logger.error("Performance page error: %s", e)
        text = _msg(lang, {
            "EN": f"{Icons.DASHBOARD} <b>Performance Dashboard</b>\n\nNo data yet. Start trading to see your stats here.\n\n{Icons.CHART} Charts and detailed reports coming soon.",
            "AR": f"{Icons.DASHBOARD} <b>لوحة الأداء</b>\n\nلا توجد بيانات بعد. ابدأ التداول لترى إحصائياتك هنا.\n\n{Icons.CHART} الرسوم البيانية والتقارير قريباً.",
            "FR": f"{Icons.DASHBOARD} <b>Tableau de Performance</b>\n\nPas encore de données. Commencez à trader pour voir vos stats.\n\n{Icons.CHART} Graphiques et rapports détaillés à venir.",
            "ES": f"{Icons.DASHBOARD} <b>Panel de Rendimiento</b>\n\nSin datos aún. Empieza a operar para ver tus estadísticas.\n\n{Icons.CHART} Gráficos e informes detallados próximamente.",
        })

    await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=_back_btn(lang))


TICKET_CATEGORIES = [
    "connection",
    "license",
    "performance",
    "billing",
    "account",
    "bug",
    "other",
]

def _cat_label(cat: str, lang: str) -> str:
    labels = {
        "connection": {"EN": "🔌 Connection Issue", "AR": "🔌 مشكلة اتصال", "FR": "🔌 Problème de connexion", "ES": "🔌 Problema de conexión"},
        "license": {"EN": "🔑 License Problem", "AR": "🔑 مشكلة رخصة", "FR": "🔑 Problème de licence", "ES": "🔑 Problema de licencia"},
        "performance": {"EN": "📊 Performance Issue", "AR": "📊 مشكلة أداء", "FR": "📊 Problème de performance", "ES": "📊 Problema de rendimiento"},
        "billing": {"EN": "💰 Billing", "AR": "💰 الفوترة", "FR": "💰 Facturation", "ES": "💰 Facturación"},
        "account": {"EN": "👤 Account Problem", "AR": "👤 مشكلة حساب", "FR": "👤 Problème de compte", "ES": "👤 Problema de cuenta"},
        "bug": {"EN": "🐛 Bug Report", "AR": "🐛 بلاغ خطأ", "FR": "🐛 Rapport de bug", "ES": "🐛 Reporte de error"},
        "other": {"EN": "📝 Other", "AR": "📝 أخرى", "FR": "📝 Autre", "ES": "📝 Otro"},
    }
    return labels.get(cat, labels["other"]).get(lang, labels["other"]["EN"])


async def handle_support_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    lang = context.user_data.get("language", "EN")
    tg_user = update.effective_user

    # Show license info + create ticket option
    try:
        async with async_session_factory() as session:
            user_repo = UserRepository(session)
            lic_repo = LicenseRepository(session)
            user = await user_repo.get_by_telegram_id(tg_user.id)
            license_info = ""
            if user:
                licenses = await lic_repo.get_by_user_id(user.id)
                active = [l for l in licenses if l.status == "active"]
                if active:
                    lic = active[0]
                    license_info = _msg(lang, {
                        "EN": f"\n{Icons.LICENSE} License: <code>{lic.license_key}</code> ({lic.plan})",
                        "AR": f"\n{Icons.LICENSE} الرخصة: <code>{lic.license_key}</code> ({lic.plan})",
                        "FR": f"\n{Icons.LICENSE} Licence: <code>{lic.license_key}</code> ({lic.plan})",
                        "ES": f"\n{Icons.LICENSE} Licencia: <code>{lic.license_key}</code> ({lic.plan})",
                    })
                else:
                    license_info = _msg(lang, {
                        "EN": f"\n{Icons.LICENSE} No active license",
                        "AR": f"\n{Icons.LICENSE} لا توجد رخصة نشطة",
                        "FR": f"\n{Icons.LICENSE} Aucune licence active",
                        "ES": f"\n{Icons.LICENSE} Sin licencia activa",
                    })
    except Exception as e:
        logger.error("Support page error: %s", e)
        license_info = ""

    text = _msg(lang, {
        "EN": (
            f"{Icons.SUPPORT} <b>Support</b>\n\n"
            f"Hello {tg_user.first_name or ''}!{license_info}\n\n"
            f"Click below to create a support ticket. Our team will respond within 24h."
        ),
        "AR": (
            f"{Icons.SUPPORT} <b>الدعم</b>\n\n"
            f"مرحباً {tg_user.first_name or ''}!{license_info}\n\n"
            f"اضغط أدناه لإنشاء تذكرة دعم. سوف يرد فريقنا خلال 24 ساعة."
        ),
        "FR": (
            f"{Icons.SUPPORT} <b>Support</b>\n\n"
            f"Bonjour {tg_user.first_name or ''}!{license_info}\n\n"
            f"Cliquez ci-dessous pour créer un ticket. Notre équipe répondra sous 24h."
        ),
        "ES": (
            f"{Icons.SUPPORT} <b>Soporte</b>\n\n"
            f"Hola {tg_user.first_name or ''}!{license_info}\n\n"
            f"Haz clic abajo para crear un ticket. Responderemos dentro de 24h."
        ),
    })

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            {"EN": "📩 Create Ticket", "AR": "📩 إنشاء تذكرة", "FR": "📩 Créer un Ticket", "ES": "📩 Crear Ticket"}
            .get(lang, "📩 Create Ticket"),
            callback_data="TICKET:CREATE"
        )],
        [InlineKeyboardButton(
            {"EN": "🎫 My Tickets", "AR": "🎫 تذاكري", "FR": "🎫 Mes Tickets", "ES": "🎫 Mis Tickets"}
            .get(lang, "🎫 My Tickets"),
            callback_data="TICKET:LIST"
        )],
        [InlineKeyboardButton(
            {"EN": "⬅️ Back", "AR": "⬅️ رجوع", "FR": "⬅️ Retour", "ES": "⬅️ Volver"}
            .get(lang, "⬅️ Back"),
            callback_data="NAV:BACK"
        )],
    ])
    await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=kb)


async def handle_ticket_create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    lang = context.user_data.get("language", "EN")

    buttons = []
    row = []
    for i, cat in enumerate(TICKET_CATEGORIES):
        label = _cat_label(cat, lang)
        row.append(InlineKeyboardButton(label, callback_data=f"TICKET:CAT:{cat}"))
        if len(row) == 2 or i == len(TICKET_CATEGORIES) - 1:
            buttons.append(row)
            row = []

    kb = InlineKeyboardMarkup(buttons + [[
        InlineKeyboardButton(
            {"EN": "⬅️ Back", "AR": "⬅️ رجوع", "FR": "⬅️ Retour", "ES": "⬅️ Volver"}
            .get(lang, "⬅️ Back"),
            callback_data="MENU:SUPPORT"
        )
    ]])

    text = _msg(lang, {
        "EN": f"{Icons.SUPPORT} <b>Select Issue Type</b>\n\nPlease choose the category that best describes your issue:",
        "AR": f"{Icons.SUPPORT} <b>اختر نوع المشكلة</b>\n\nاختر الفئة التي تصف مشكلتك:",
        "FR": f"{Icons.SUPPORT} <b>Sélectionnez le type de problème</b>\n\nChoisissez la catégorie qui décrit le mieux votre problème:",
        "ES": f"{Icons.SUPPORT} <b>Selecciona el tipo de problema</b>\n\nElige la categoría que mejor describa tu problema:",
    })
    await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=kb)


async def handle_ticket_category(update: Update, context: ContextTypes.DEFAULT_TYPE, category: str):
    query = update.callback_query
    lang = context.user_data.get("language", "EN")

    context.user_data["ticket_category"] = category

    if category == "other":
        context.user_data["waiting_for"] = "TICKET_OTHER_CAT"
        text = _msg(lang, {
            "EN": f"{Icons.SUPPORT} <b>Custom Category</b>\n\nPlease type your issue category:",
            "AR": f"{Icons.SUPPORT} <b>فئة مخصصة</b>\n\nاكتب فئة مشكلتك:",
            "FR": f"{Icons.SUPPORT} <b>Catégorie personnalisée</b>\n\nTapez la catégorie de votre problème:",
            "ES": f"{Icons.SUPPORT} <b>Categoría personalizada</b>\n\nEscribe la categoría de tu problema:",
        })
        cancel_btn = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                {"EN": "⬅️ Back", "AR": "⬅️ رجوع", "FR": "⬅️ Retour", "ES": "⬅️ Volver"}
                .get(lang, "⬅️ Back"),
                callback_data="TICKET:CREATE"
            )
        ]])
        await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=cancel_btn)
        return

    context.user_data["waiting_for"] = "TICKET_DESCRIPTION"
    cat_label = _cat_label(category, lang)
    text = _msg(lang, {
        "EN": (
            f"{Icons.SUPPORT} <b>Describe your issue</b>\n\n"
            f"Category: {cat_label}\n\n"
            f"Please describe the problem in detail. Include steps, error messages, or anything that helps us understand."
        ),
        "AR": (
            f"{Icons.SUPPORT} <b>صِف مشكلتك</b>\n\n"
            f"الفئة: {cat_label}\n\n"
            f"صِف المشكلة بالتفصيل. أضف الخطوات، رسائل الخطأ أو أي شيء يساعدنا على فهم المشكلة."
        ),
        "FR": (
            f"{Icons.SUPPORT} <b>Décrivez votre problème</b>\n\n"
            f"Catégorie: {cat_label}\n\n"
            f"Décrivez le problème en détail. Incluez les étapes, messages d'erreur ou tout ce qui peut nous aider."
        ),
        "ES": (
            f"{Icons.SUPPORT} <b>Describe tu problema</b>\n\n"
            f"Categoría: {cat_label}\n\n"
            f"Describe el problema en detalle. Incluye pasos, mensajes de error o cualquier cosa que nos ayude."
        ),
    })
    cancel_btn = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            {"EN": "⬅️ Back", "AR": "⬅️ رجوع", "FR": "⬅️ Retour", "ES": "⬅️ Volver"}
            .get(lang, "⬅️ Back"),
            callback_data="TICKET:CREATE"
        )
    ]])
    await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=cancel_btn)
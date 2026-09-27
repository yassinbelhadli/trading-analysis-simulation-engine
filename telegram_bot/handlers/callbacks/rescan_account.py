from telegram import Update
from telegram.ext import ContextTypes

from database.db import async_session_factory
from database.repositories import UserRepository
from core_engine.account_manager import AccountManager
from security.encryption import decrypt
from telegram_bot.services.mt_connector import mt_connector, MTLoginData
from telegram_bot.services.account_verification_service import account_scanner
from telegram_bot.ui.keyboards.accounts import account_detail_keyboard
from core_engine.engine_manager import engine_manager


async def handle_account_rescan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    lang = context.user_data.get("language", "EN")
    tg_user = update.effective_user
    account_id = query.data.rsplit(":", 1)[1] if ":" in query.data else ""

    await query.edit_message_text(
        text=_msg(lang, "SCANNING"),
        parse_mode="HTML",
    )

    async with async_session_factory() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(tg_user.id)
        if not user:
            await query.edit_message_text("❌ User not found.")
            return

        mgr = AccountManager(session)
        account = await mgr.get_account(account_id)
        if not account or account.user_id != user.id:
            await query.edit_message_text("❌ Account not found.")
            return

        # decrypt password
        pw = decrypt(account.encrypted_password) if account.encrypted_password else None

        login_data = MTLoginData(
            platform=account.platform or "MT5",
            server=account.server or "",
            login=account.login or "",
            password=pw or "",
        )

    # scan
    result = await mt_connector.test_connection(login_data)
    if not result.success:
        await query.edit_message_text(
            text=_msg(lang, "CONNECTION_FAILED"),
            parse_mode="HTML",
            reply_markup=account_detail_keyboard(account_id, account.engine_status, engine_manager.is_running(account_id), lang),
        )
        return

    report = await account_scanner.run_full_scan(
        login_data=login_data,
        scan_result=result,
        setup_data={},
        user_data={},
        account_id=account_id,
    )

    # update snapshots
    if report.account:
        async with async_session_factory() as session:
            mgr = AccountManager(session)
            if report.account.balance:
                await mgr.update_balance(account_id, report.account.balance)
            if report.account.equity:
                await mgr.update_equity(account_id, report.account.equity)
            await session.commit()

    # format mini-report
    lines = [
        f"🔄 <b>{_msg(lang, 'RESCAN_COMPLETE')}</b>",
        "",
    ]
    if report.account:
        lines.append(f"<b>Balance:</b> ${_fmt(report.account.balance)}")
        lines.append(f"<b>Equity:</b> ${_fmt(report.account.equity)}")
    lines.append(f"<b>Connection:</b> {'✅ OK' if report.connection.success else '❌ Failed'}")
    if report.comparison and report.comparison.items:
        for v in report.comparison.items:
            if v.status != "match":
                lines.append(f"<b>{v.field}:</b> {v.expected} vs {v.actual}")

    await query.edit_message_text(
        text="\n".join(lines),
        parse_mode="HTML",
        reply_markup=account_detail_keyboard(account_id, account.engine_status, engine_manager.is_running(account_id), lang),
    )


def _fmt(val):
    if val is None:
        return "—"
    try:
        v = float(val)
        if v >= 1000000:
            return f"{v/1000000:.2f}M"
        if v >= 1000:
            return f"{v/1000:.2f}K"
        return f"{v:.2f}"
    except (ValueError, TypeError):
        return str(val)


def _msg(lang: str, key: str) -> str:
    msgs = {
        "SCANNING": {
            "EN": "🔄 <b>Scanning account...</b>\n\nConnecting to MT5 and fetching data.",
            "FR": "🔄 <b>Scan du compte...</b>\n\nConnexion à MT5 et récupération des données.",
            "AR": "🔄 <b>جاري فحص الحساب...</b>\n\nالاتصال بـ MT5 وجلب البيانات.",
            "ES": "🔄 <b>Escaneando cuenta...</b>\n\nConectando a MT5 y obteniendo datos.",
        },
        "CONNECTION_FAILED": {
            "EN": "❌ <b>Connection Failed</b>\n\nCould not connect to the trading account.\nCheck if the server/password is still valid.",
            "FR": "❌ <b>Échec de connexion</b>\n\nImpossible de se connecter au compte de trading.\nVérifiez que le serveur/mot de passe est toujours valide.",
            "AR": "❌ <b>فشل الاتصال</b>\n\nتعذر الاتصال بحساب التداول.\nتحقق من صحة السيرفر/كلمة المرور.",
            "ES": "❌ <b>Conexión fallida</b>\n\nNo se pudo conectar a la cuenta de trading.\nVerifica que el servidor/contraseña sigue siendo válido.",
        },
        "RESCAN_COMPLETE": {
            "EN": "Rescan Complete",
            "FR": "Scan terminé",
            "AR": "اكتمل الفحص",
            "ES": "Escaneo completado",
        },
    }
    return msgs.get(key, {}).get(lang, msgs.get(key, {}).get("EN", key))

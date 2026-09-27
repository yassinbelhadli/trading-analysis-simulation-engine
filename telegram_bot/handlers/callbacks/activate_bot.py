from telegram import Update
from telegram.ext import ContextTypes

from database.db import async_session_factory
from database.repositories import UserRepository
from core_engine.account_manager import AccountManager
from core_engine.engine_manager import engine_manager
from telegram_bot.ui.keyboards.accounts import account_detail_keyboard


async def handle_activate_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    lang = context.user_data.get("language", "EN")
    tg_user = update.effective_user

    async with async_session_factory() as session:
        user_repo = UserRepository(session)
        acc_mgr = AccountManager(session)

        user = await user_repo.get_by_telegram_id(tg_user.id)
        if not user:
            await query.edit_message_text(text=_msg(lang, "NO_USER"))
            return

        accounts = await acc_mgr.acc_repo.get_awaiting_activation(user.id)
        if not accounts:
            await query.edit_message_text(text=_msg(lang, "NO_ACCOUNTS"))
            return

        account = accounts[0]

        if not account.license_id:
            await query.edit_message_text(text=_msg(lang, "NO_LICENSE"))
            return

        if not account.verified:
            await query.edit_message_text(text=_msg(lang, "NOT_VERIFIED"))
            return

        await acc_mgr.activate_account(account.id)
        await session.commit()

    await engine_manager.start(account.id)

    # delete old scan_report message
    scan_msg_id = context.user_data.pop("scan_message_id", None)
    if scan_msg_id:
        try:
            await query.message.chat.delete_message(scan_msg_id)
        except Exception:
            pass

    # edit current message to success + account management keyboard
    await query.edit_message_text(
        text=_msg(lang, "SUCCESS"),
        parse_mode="HTML",
        reply_markup=account_detail_keyboard(account.id, "ACTIVE", True, lang),
    )


def _msg(lang: str, key: str) -> str:
    msgs = {
        "NO_USER": {
            "EN": "❌ User not found. Please start with /start",
            "FR": "❌ Utilisateur introuvable. Commencez par /start",
            "AR": "❌ المستخدم غير موجود. ابدأ بـ /start",
            "ES": "❌ Usuario no encontrado. Empieza con /start",
        },
        "NO_ACCOUNTS": {
            "EN": "❌ No accounts waiting for activation.\nSave a setup first.",
            "FR": "❌ Aucun compte en attente d'activation.\nEnregistrez d'abord une configuration.",
            "AR": "❌ لا توجد حسابات في انتظار التفعيل.\nاحفظ إعداداً أولاً.",
            "ES": "❌ No hay cuentas esperando activación.\nGuarda una configuración primero.",
        },
        "NO_LICENSE": {
            "EN": "❌ No license linked to this account.\nBind a license first.",
            "FR": "❌ Aucune licence liée à ce compte.\nLiez une licence d'abord.",
            "AR": "❌ لا يوجد ترخيص مرتبط بهذا الحساب.\nاربط ترخيصاً أولاً.",
            "ES": "❌ Sin licencia vinculada a esta cuenta.\nVincula una licencia primero.",
        },
        "NOT_VERIFIED": {
            "EN": "❌ Account is not verified.\nPlease re-save your setup.",
            "FR": "❌ Le compte n'est pas vérifié.\nVeuillez ré-enregistrer votre configuration.",
            "AR": "❌ الحساب غير موثّق.\nأعد حفظ إعداداتك من فضلك.",
            "ES": "❌ La cuenta no está verificada.\nVuelve a guardar tu configuración.",
        },
        "SUCCESS": {
            "EN": "🚀 <b>Bot Activated Successfully</b>\n\n"
                  "Your trading engine is now running.\n"
                  "Use /dashboard to monitor your account.",
            "FR": "🚀 <b>Bot activé avec succès</b>\n\n"
                  "Votre moteur de trading est maintenant actif.\n"
                  "Utilisez /dashboard pour suivre votre compte.",
            "AR": "🚀 <b>تم تشغيل البوت بنجاح</b>\n\n"
                  "محرك التداول شغال الآن.\n"
                  "استعمل /dashboard لمتابعة حسابك.",
            "ES": "🚀 <b>Bot activado correctamente</b>\n\n"
                  "Tu motor de trading ya está funcionando.\n"
                  "Usa /dashboard para monitorear tu cuenta.",
        },
    }
    return msgs.get(key, {}).get(lang, msgs.get(key, {}).get("EN", key))

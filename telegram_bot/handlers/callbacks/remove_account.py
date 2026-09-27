from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database.db import async_session_factory
from database.repositories import UserRepository, AccountRepository
from database.repositories.audit_repository import AuditRepository
from database.models import AuditLog
from telegram_bot.ui.keyboards.accounts import account_detail_keyboard
from telegram_bot.ui.keyboards.menu import main_menu_keyboard
from telegram_bot.handlers.callbacks.account_detail import handle_account_detail
from core_engine.engine_manager import engine_manager


async def handle_account_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    lang = context.user_data.get("language", "EN")
    tg_user = update.effective_user
    account_id = query.data.rsplit(":", 1)[1] if ":" in query.data else ""

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

    header = account.name or f"{account.server or account.platform} #{account.login or ''}"

    text = _msg(lang, "CONFIRM_TITLE").format(name=header) + "\n\n" + _msg(lang, "CONFIRM_DETAILS")

    await query.edit_message_text(
        text=text,
        parse_mode="HTML",
        reply_markup=_remove_confirm_keyboard(account_id, lang),
    )


async def handle_account_remove_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    lang = context.user_data.get("language", "EN")
    tg_user = update.effective_user
    account_id = query.data.rsplit(":", 1)[1] if ":" in query.data else ""

    async with async_session_factory() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(tg_user.id)
        if not user:
            await query.edit_message_text(text=_msg(lang, "NOT_FOUND"))
            return

        acc_repo = AccountRepository(session)

        # stop engine in memory if running
        if engine_manager.is_running(account_id):
            await engine_manager.stop(account_id)

        # soft-remove account
        try:
            await acc_repo.remove_account(account_id, user.id)
            await session.commit()
        except Exception:
            await session.rollback()
            await query.edit_message_text(text=_msg(lang, "ERROR"))
            return

    # also create audit log entry
    try:
        async with async_session_factory() as session:
            audit = AuditLog(
                user_id=user.id,
                account_id=account_id,
                action="ACCOUNT_REMOVED",
                details="Account removed by user via Telegram",
            )
            await AuditRepository(session).add(audit)
            await session.commit()
    except Exception:
        pass

    await query.edit_message_text(
        text=_msg(lang, "SUCCESS"),
        parse_mode="HTML",
        reply_markup=_back_to_main_keyboard(lang),
    )


async def handle_account_remove_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    lang = context.user_data.get("language", "EN")
    account_id = query.data.rsplit(":", 1)[1] if ":" in query.data else ""

    await handle_account_detail(update, context)


def _remove_confirm_keyboard(account_id: str, lang: str = "EN"):
    labels = {
        "EN": ("✅ Confirm Remove", "❌ Cancel"),
        "FR": ("✅ Confirmer la suppression", "❌ Annuler"),
        "AR": ("✅ تأكيد الحذف", "❌ إلغاء"),
        "ES": ("✅ Confirmar", "❌ Cancelar"),
    }
    t = labels.get(lang, labels["EN"])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t[0], callback_data=f"ACCOUNT:REMOVE_CONFIRM:{account_id}")],
        [InlineKeyboardButton(t[1], callback_data=f"ACCOUNT:REMOVE_CANCEL:{account_id}")],
    ])


def _back_to_main_keyboard(lang: str = "EN"):
    return main_menu_keyboard(lang)


def _msg(lang: str, key: str) -> str:
    msgs = {
        "NOT_FOUND": {
            "EN": "❌ Account not found.",
            "FR": "❌ Compte introuvable.",
            "AR": "❌ الحساب غير موجود.",
            "ES": "❌ Cuenta no encontrada.",
        },
        "CONFIRM_TITLE": {
            "EN": "⚠️ <b>Remove {name}</b>\n\nAre you sure you want to remove this account?",
            "FR": "⚠️ <b>Supprimer {name}</b>\n\nÊtes-vous sûr de vouloir supprimer ce compte ?",
            "AR": "⚠️ <b>حذف {name}</b>\n\nهل أنت متأكد أنك تريد حذف هذا الحساب؟",
            "ES": "⚠️ <b>Eliminar {name}</b>\n\n¿Estás seguro de que quieres eliminar esta cuenta?",
        },
        "CONFIRM_DETAILS": {
            "EN": "This action will:\n• Stop the engine\n• Stop the scanner\n• Unlink the license\n• Clear credentials\n• Allow re-adding the account later",
            "FR": "Cette action va :\n• Arrêter le moteur\n• Arrêter le scanner\n• Délier la licence\n• Effacer les identifiants\n• Permettre de rajouter le compte plus tard",
            "AR": "سيتم:\n• إيقاف المحرك\n• إيقاف الماسح\n• فك الترخيص\n• مسح بيانات الدخول\n• السماح بإعادة ربط الحساب لاحقاً",
            "ES": "Esta acción:\n• Detendrá el motor\n• Detendrá el escáner\n• Desvinculará la licencia\n• Borrará las credenciales\n• Permitirá volver a añadir la cuenta después",
        },
        "SUCCESS": {
            "EN": "✅ <b>Account Removed</b>\n\nThe account has been removed successfully.\nYou can add it again anytime.",
            "FR": "✅ <b>Compte supprimé</b>\n\nLe compte a été supprimé avec succès.\nVous pouvez le rajouter à tout moment.",
            "AR": "✅ <b>تم حذف الحساب</b>\n\nتم حذف الحساب بنجاح.\nيمكنك إضافته مرة أخرى في أي وقت.",
            "ES": "✅ <b>Cuenta eliminada</b>\n\nLa cuenta se ha eliminado correctamente.\nPuedes volver a añadirla cuando quieras.",
        },
        "ERROR": {
            "EN": "❌ Failed to remove account. Please try again.",
            "FR": "❌ Échec de la suppression. Veuillez réessayer.",
            "AR": "❌ فشل حذف الحساب. حاول مرة أخرى.",
            "ES": "❌ Error al eliminar la cuenta. Intenta de nuevo.",
        },
    }
    return msgs.get(key, {}).get(lang, msgs.get(key, {}).get("EN", key))

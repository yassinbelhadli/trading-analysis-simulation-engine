from telegram import Update
from telegram.ext import ContextTypes

from database.db import async_session_factory
from database.repositories import AccountRepository, UserRepository
from telegram_bot.handlers.callbacks.account_detail import handle_account_detail


async def handle_account_rename(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    lang = context.user_data.get("language", "EN")
    account_id = query.data.rsplit(":", 1)[1] if ":" in query.data else ""

    context.user_data["rename_account_id"] = account_id
    context.user_data["waiting_for"] = "ACCOUNT_RENAME"

    await query.edit_message_text(
        text=_msg(lang, "PROMPT"),
        parse_mode="HTML",
    )


async def handle_rename_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    lang = context.user_data.get("language", "EN")

    if len(text) > 60:
        await update.message.reply_text(_msg(lang, "TOO_LONG"))
        return
    if not text:
        await update.message.reply_text(_msg(lang, "EMPTY"))
        return

    account_id = context.user_data.get("rename_account_id")
    if not account_id:
        await update.message.reply_text("❌ Session expired.")
        return

    async with async_session_factory() as session:
        repo = AccountRepository(session)
        account = await repo.get_by_id(account_id)
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(update.effective_user.id)

        if not account or not user or account.user_id != user.id:
            await update.message.reply_text("❌ Account not found.")
            context.user_data["waiting_for"] = None
            return

        account.name = text
        await session.commit()

    context.user_data["waiting_for"] = None
    context.user_data.pop("rename_account_id", None)

    await update.message.reply_text(
        _msg(lang, "SUCCESS").format(name=text),
        parse_mode="HTML",
    )


def _msg(lang: str, key: str) -> str:
    msgs = {
        "PROMPT": {
            "EN": "✏️ <b>Rename Account</b>\n\nSend me the new name for this account\n(max 60 characters):",
            "FR": "✏️ <b>Renommer le compte</b>\n\nEnvoyez le nouveau nom pour ce compte\n(60 caractères max) :",
            "AR": "✏️ <b>إعادة تسمية الحساب</b>\n\nأرسل الاسم الجديد لهذا الحساب\n(60 حرف كحد أقصى):",
            "ES": "✏️ <b>Renombrar cuenta</b>\n\nEnvía el nuevo nombre para esta cuenta\n(máx. 60 caracteres):",
        },
        "TOO_LONG": {
            "EN": "❌ Name is too long. Maximum 60 characters.",
            "FR": "❌ Le nom est trop long. Maximum 60 caractères.",
            "AR": "❌ الاسم طويل جداً. الحد الأقصى 60 حرفاً.",
            "ES": "❌ El nombre es demasiado largo. Máximo 60 caracteres.",
        },
        "EMPTY": {
            "EN": "❌ Name cannot be empty.",
            "FR": "❌ Le nom ne peut pas être vide.",
            "AR": "❌ الاسم لا يمكن أن يكون فارغاً.",
            "ES": "❌ El nombre no puede estar vacío.",
        },
        "SUCCESS": {
            "EN": "✅ <b>Account renamed</b>\n\nNew name: {name}",
            "FR": "✅ <b>Compte renommé</b>\n\nNouveau nom : {name}",
            "AR": "✅ <b>تمت إعادة تسمية الحساب</b>\n\nالاسم الجديد: {name}",
            "ES": "✅ <b>Cuenta renombrada</b>\n\nNuevo nombre: {name}",
        },
    }
    return msgs.get(key, {}).get(lang, msgs.get(key, {}).get("EN", key))

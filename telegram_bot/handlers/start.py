from telegram import Update
from telegram.ext import ContextTypes

from database.db import async_session_factory
from database.repositories import UserRepository, LicenseRepository, AccountRepository
from telegram_bot.ui.keyboards.language import language_keyboard
from telegram_bot.ui.keyboards.menu import main_menu_keyboard
from telegram_bot.ui.keyboards.license_keyboard import no_license_keyboard
from telegram_bot.ui.keyboards.activation import activation_keyboard
from telegram_bot.services.navigation import reset_navigation


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("waiting_for", None)
    context.user_data.pop("mt_server", None)
    context.user_data.pop("mt_login", None)
    context.user_data.pop("mt_password", None)
    context.user_data.pop("encrypted_password", None)
    context.user_data.pop("scan_message_id", None)
    context.user_data.pop("confirm_message_id", None)
    context.user_data.pop("existing_account_id", None)

    tg_user = update.effective_user

    async with async_session_factory() as session:
        user_repo = UserRepository(session)
        lic_repo = LicenseRepository(session)
        acc_repo = AccountRepository(session)

        user = await user_repo.get_by_telegram_id(tg_user.id)

        # Case 1: New user (no DB record yet)
        if not user:
            text = (
                "🚀 <b>ICT Funded EA Pro</b>\n\n"
                "Welcome!\n\n"
                "Please select your language:"
            )
            await update.effective_message.reply_text(text=text, parse_mode="HTML", reply_markup=language_keyboard())
            return

        lang = user.language or "EN"
        context.user_data["language"] = lang

        # Check for active license
        licenses = await lic_repo.get_by_user_id(user.id)
        active_license = any(l.status == "active" for l in licenses)

        if not active_license:
            text = get_msg(lang, {
                "EN": "❌ <b>No Active License</b>\n\nYou don't have an active license.\n\nBuy or enter a license key to start trading.",
                "FR": "❌ <b>Aucune licence active</b>\n\nVous n'avez pas de licence active.\n\nAchetez ou entrez une clé de licence pour commencer.",
                "AR": "❌ <b>لا توجد رخصة نشطة</b>\n\nليست لديك رخصة نشطة.\n\nاشترِ أو أدخل مفتاح ترخيص لبدء التداول.",
                "ES": "❌ <b>Sin licencia activa</b>\n\nNo tienes una licencia activa.\n\nCompra o ingresa una clave de licencia para empezar.",
            })
            await update.effective_message.reply_text(text=text, parse_mode="HTML", reply_markup=no_license_keyboard(lang))
            context.user_data["waiting_for"] = None
            return

        # Check linked accounts
        accounts = await acc_repo.get_by_user_id(user.id)
        accounts = [a for a in accounts if a.removed_at is None]

        if not accounts:
            text = get_msg(lang, {
                "EN": "✅ <b>License Active</b>\n\nYour license is active. Add an account to start trading.",
                "FR": "✅ <b>Licence active</b>\n\nVotre licence est active. Ajoutez un compte pour commencer.",
                "AR": "✅ <b>الرخصة نشطة</b>\n\nرخصتك نشطة. أضف حساباً لبدء التداول.",
                "ES": "✅ <b>Licencia activa</b>\n\nTu licencia está activa. Añade una cuenta para empezar.",
            })
            await update.effective_message.reply_text(text=text, parse_mode="HTML")
            # show main menu anyway
            reset_navigation(context)
            await update.effective_message.reply_text(
                text=get_msg(lang, {
                    "EN": "🏠 <b>Main Menu</b>",
                    "FR": "🏠 <b>Menu Principal</b>",
                    "AR": "🏠 <b>القائمة الرئيسية</b>",
                    "ES": "🏠 <b>Menú Principal</b>",
                }),
                parse_mode="HTML",
                reply_markup=main_menu_keyboard(lang),
            )
            return

        # Case 3: Has accounts
        reset_navigation(context)
        active_count = sum(1 for a in accounts if a.active and a.engine_status == "ACTIVE")
        text = get_msg(lang, {
            "EN": "🏠 <b>Main Menu</b>\n\n"
                  f"Welcome back, {tg_user.first_name or tg_user.username or ''}!\n"
                  f"Accounts: <b>{len(accounts)}</b> total, <b>{active_count}</b> active",
            "FR": "🏠 <b>Menu Principal</b>\n\n"
                  f"Bon retour, {tg_user.first_name or tg_user.username or ''}!\n"
                  f"Comptes: <b>{len(accounts)}</b> total, <b>{active_count}</b> actif(s)",
            "AR": "🏠 <b>القائمة الرئيسية</b>\n\n"
                  f"مرحباً بعودتك، {tg_user.first_name or tg_user.username or ''}!\n"
                  f"الحسابات: <b>{len(accounts)}</b> إجمالي، <b>{active_count}</b> نشط",
            "ES": "🏠 <b>Menú Principal</b>\n\n"
                  f"Bienvenido de nuevo, {tg_user.first_name or tg_user.username or ''}!\n"
                  f"Cuentas: <b>{len(accounts)}</b> total, <b>{active_count}</b> activa(s)",
        })
        await update.effective_message.reply_text(text=text, parse_mode="HTML", reply_markup=main_menu_keyboard(lang))


def get_msg(lang, messages):
    return messages.get(lang, messages["EN"])

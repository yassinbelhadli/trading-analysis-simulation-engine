from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database.db import async_session_factory
from database.repositories import UserRepository, AccountRepository, LicenseRepository
from telegram_bot.services.navigation import push_page, pop_page, reset_navigation, PAGE_MAIN, PAGE_ACCOUNTS, PAGE_ACTIVE
from telegram_bot.ui.keyboards.menu import main_menu_keyboard, back_keyboard
from telegram_bot.ui.keyboards.accounts import accounts_list_keyboard, account_detail_keyboard
from telegram_bot.ui.keyboards.activation import activation_keyboard
from telegram_bot.ui.keyboards.license_keyboard import no_license_keyboard
from telegram_bot.ui.keyboards.account_type import account_type_keyboard
from telegram_bot.ui.keyboards.language import language_keyboard
from telegram_bot.services.setup import get_setup


async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    lang = context.user_data.get("language", "EN")
    reset_navigation(context)

    tg_user = update.effective_user
    async with async_session_factory() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(tg_user.id)

        active_count = 0
        if user:
            accs = await AccountRepository(session).get_by_user_id(user.id)
            active_count = sum(1 for a in accs if a.active and a.engine_status == "ACTIVE" and a.removed_at is None)

    text = get_msg(lang, {
        "EN": f"🏠 <b>Main Menu</b>\n\nUser: {tg_user.first_name or tg_user.username or tg_user.id}\nActive Accounts: {active_count}",
        "FR": f"🏠 <b>Menu Principal</b>\n\nUtilisateur: {tg_user.first_name or tg_user.username or tg_user.id}\nComptes actifs: {active_count}",
        "AR": f"🏠 <b>القائمة الرئيسية</b>\n\nالمستخدم: {tg_user.first_name or tg_user.username or tg_user.id}\nالحسابات النشطة: {active_count}",
        "ES": f"🏠 <b>Menú Principal</b>\n\nUsuario: {tg_user.first_name or tg_user.username or tg_user.id}\nCuentas activas: {active_count}",
    }) if user else (
        "❌ No account found. Please use /start to begin."
    )

    await query.edit_message_text(
        text=text,
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(lang),
    )
    context.user_data["waiting_for"] = None


async def handle_my_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    lang = context.user_data.get("language", "EN")
    push_page(context, PAGE_ACCOUNTS)
    tg_user = update.effective_user

    async with async_session_factory() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(tg_user.id)
        if not user:
            await query.edit_message_text("❌ User not found. Use /start")
            return

        acc_repo = AccountRepository(session)
        accounts = await acc_repo.get_by_user_id(user.id)
        # filter out soft-removed
        accounts = [a for a in accounts if a.removed_at is None]

    if not accounts:
        text = get_msg(lang, {
            "EN": "📂 <b>My Accounts</b>\n\nNo accounts yet.\nPress ➕ Add Account to start.",
            "FR": "📂 <b>Mes Comptes</b>\n\nAucun compte pour le moment.\nAppuyez sur ➕ Ajouter un Compte.",
            "AR": "📂 <b>حساباتي</b>\n\nلا توجد حسابات بعد.\nاضغط ➕ إضافة حساب للبدء.",
            "ES": "📂 <b>Mis Cuentas</b>\n\nAún no hay cuentas.\nPresiona ➕ Añadir Cuenta para empezar.",
        })
        await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=_accounts_empty_keyboard(lang))
        return

    text = get_msg(lang, {
        "EN": "📂 <b>My Accounts</b>\n\nSelect an account to manage:",
        "FR": "📂 <b>Mes Comptes</b>\n\nSélectionnez un compte à gérer :",
        "AR": "📂 <b>حساباتي</b>\n\nاختر حساباً للإدارة:",
        "ES": "📂 <b>Mis Cuentas</b>\n\nSelecciona una cuenta para gestionar:",
    })
    await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=accounts_list_keyboard(accounts, lang))


async def handle_active_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    lang = context.user_data.get("language", "EN")
    push_page(context, PAGE_ACTIVE)
    tg_user = update.effective_user

    async with async_session_factory() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(tg_user.id)
        if not user:
            await query.edit_message_text("❌ User not found. Use /start")
            return

        acc_repo = AccountRepository(session)
        accounts = await acc_repo.get_active_by_user_id(user.id)

    if not accounts:
        text = get_msg(lang, {
            "EN": "🟢 <b>Active Accounts</b>\n\nNo active accounts.\nAdd and activate an account first.",
            "FR": "🟢 <b>Comptes Actifs</b>\n\nAucun compte actif.\nAjoutez et activez d'abord un compte.",
            "AR": "🟢 <b>الحسابات النشطة</b>\n\nلا توجد حسابات نشطة.\nأضف حساباً وفعّله أولاً.",
            "ES": "🟢 <b>Cuentas Activas</b>\n\nNo hay cuentas activas.\nAñade y activa una cuenta primero.",
        })
        await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=back_keyboard(lang))
        return

    text = get_msg(lang, {
        "EN": "🟢 <b>Active Accounts</b>\n\nSelect an account:",
        "FR": "🟢 <b>Comptes Actifs</b>\n\nSélectionnez un compte :",
        "AR": "🟢 <b>الحسابات النشطة</b>\n\nاختر حساباً:",
        "ES": "🟢 <b>Cuentas Activas</b>\n\nSelecciona una cuenta:",
    })
    await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=accounts_list_keyboard(accounts, lang))


async def handle_nav_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    lang = context.user_data.get("language", "EN")
    page = pop_page(context)

    if page == "MY_ACCOUNTS":
        await handle_my_accounts(update, context)
    elif page == "ACTIVE_ACCOUNTS":
        await handle_active_accounts(update, context)
    elif page == "ACCOUNT_DETAIL":
        # go back to accounts list
        await handle_my_accounts(update, context)
    else:
        await handle_main_menu(update, context)


async def handle_add_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    lang = context.user_data.get("language", "EN")

    context.user_data.clear()
    context.user_data["language"] = lang
    get_setup(context)

    text = get_msg(lang, {
        "EN": "📋 <b>Add Account</b>\n\nChoose your account type:",
        "FR": "📋 <b>Ajouter un Compte</b>\n\nChoisissez le type de compte :",
        "AR": "📋 <b>إضافة حساب</b>\n\nاختر نوع الحساب:",
        "ES": "📋 <b>Añadir Cuenta</b>\n\nSelecciona el tipo de cuenta:",
    })
    await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=account_type_keyboard(lang))


async def handle_change_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    context.user_data["changing_language"] = True
    await query.edit_message_text(
        text=get_msg(context.user_data.get("language", "EN"), {
            "EN": "🌐 <b>Change Language</b>\n\nSelect your preferred language:",
            "FR": "🌐 <b>Changer la Langue</b>\n\nSélectionnez votre langue préférée :",
            "AR": "🌐 <b>تغيير اللغة</b>\n\nاختر لغتك المفضلة:",
            "ES": "🌐 <b>Cambiar Idioma</b>\n\nSelecciona tu idioma preferido:",
        }),
        parse_mode="HTML",
        reply_markup=language_keyboard(),
    )


def get_msg(lang, messages):
    return messages.get(lang, messages["EN"])


def _accounts_empty_keyboard(lang: str = "EN"):
    label = {"EN": "➕ Add Account", "FR": "➕ Ajouter un Compte", "AR": "➕ إضافة حساب", "ES": "➕ Añadir Cuenta"}
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label.get(lang, "➕ Add Account"), callback_data="ADD_ACCOUNT")],
        [InlineKeyboardButton({"EN": "⬅️ Back", "FR": "⬅️ Retour", "AR": "⬅️ رجوع", "ES": "⬅️ Volver"}.get(lang, "⬅️ Back"), callback_data="NAV:BACK")],
    ])

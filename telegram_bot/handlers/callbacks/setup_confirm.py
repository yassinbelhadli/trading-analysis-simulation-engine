from telegram import Update
from telegram.ext import ContextTypes

from sqlalchemy.exc import IntegrityError

from database.db import async_session_factory
from database.repositories import UserRepository, AccountRepository, ScanRepository
from database.repositories.account_repository import (
    AccountAlreadyLinkedToUserError,
    AccountLinkedToAnotherUserError,
)
from telegram_bot.services.setup import get_setup
from telegram_bot.services.license_binding_service import LicenseBindingService
from telegram_bot.ui.keyboards.activation import activation_keyboard
from telegram_bot.ui.keyboards.license_keyboard import no_license_keyboard


async def handle_confirm_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    lang = context.user_data.get("language", "EN")
    tg_user = update.effective_user
    setup_data = get_setup(context)
    encrypted_password = context.user_data.get("encrypted_password", "")
    account_fingerprint = context.user_data.get("account_fingerprint")

    async with async_session_factory() as session:
        user_repo = UserRepository(session)
        acc_repo = AccountRepository(session)
        scan_repo = ScanRepository(session)
        binding_svc = LicenseBindingService(session)

        # 1. get or create user
        user = await user_repo.get_or_create_by_telegram(
            telegram_id=tg_user.id,
            telegram_username=tg_user.username,
            first_name=tg_user.first_name,
            last_name=tg_user.last_name,
            language=lang,
        )

        context.user_data["db_user_id"] = user.id

        # 2. check if re-binding existing unlicensed account
        existing_account_id = context.user_data.get("existing_account_id")
        if existing_account_id:
            account = await acc_repo.get_by_id(existing_account_id)
            if not account or account.user_id != user.id:
                await query.edit_message_text(text="❌ Account not found.")
                return

            # try to bind an available license to existing account
            license_bound = False
            try:
                lic = await binding_svc.find_available_license(user.id)
                if lic:
                    await binding_svc.bind_license_to_account(
                        lic.license_key, account,
                        telegram_id=tg_user.id,
                    )
                    license_bound = True
            except Exception:
                pass

            await acc_repo.verify(account.id)
            await session.commit()

            msg_key = "LICENSE_BOUND" if license_bound else "NO_LICENSE"
            await query.edit_message_text(
                text=_texts(lang, msg_key),
                parse_mode="HTML",
                reply_markup=activation_keyboard(lang) if license_bound else no_license_keyboard(lang),
            )
            context.user_data.pop("existing_account_id", None)
            return

        # 3. double-check fingerprint before creating (race-condition guard)
        existing = await acc_repo.get_bound_by_fingerprint(account_fingerprint) if account_fingerprint else None
        if existing:
            if existing.user_id == user.id and existing.license_id is not None:
                await query.edit_message_text(
                    text={
                        "EN": "ℹ️ This account is already linked to your account.\n\nYou can manage it from 'My Accounts', or remove it and link again.",
                        "FR": "ℹ️ Ce compte est déjà lié à votre compte.\n\nVous pouvez le gérer depuis 'Mes Comptes', ou le supprimer et le lier à nouveau.",
                        "AR": "ℹ️ هذا الحساب مربوط بحسابك من قبل.\n\nيمكنك إدارته من قسم 'حساباتي'، أو حذفه ثم ربطه من جديد.",
                        "ES": "ℹ️ Esta cuenta ya está vinculada a tu cuenta.\n\nPuedes gestionarla desde 'Mis Cuentas', o eliminarla y vincularla de nuevo.",
                    }.get(lang, "EN"),
                    parse_mode="HTML",
                )
                return
            if existing.user_id != user.id:
                await query.edit_message_text(
                    text={
                        "EN": "❌ Cannot link this account.\n\nThis MT4/MT5 account is linked to another user.\nIf this account is yours, contact support for safe transfer.",
                        "FR": "❌ Impossible de lier ce compte.\n\nCe compte MT4/MT5 est lié à un autre utilisateur.\nSi ce compte vous appartient, contactez le support.",
                        "AR": "❌ لا يمكن ربط هذا الحساب.\n\nحساب MT4/MT5 هذا مرتبط بمستخدم آخر.\nإذا كان الحساب ملكك، تواصل مع الدعم لنقل الربط بشكل آمن.",
                        "ES": "❌ No se puede vincular esta cuenta.\n\nEsta cuenta MT4/MT5 está vinculada a otro usuario.\nSi esta cuenta es tuya, contacta al soporte para transferirla.",
                    }.get(lang, "EN"),
                    parse_mode="HTML",
                )
                return

            # same user, no license → redirect to re-bind flow
            context.user_data["existing_account_id"] = existing.id
            account = existing
            license_bound = False
            try:
                lic = await binding_svc.find_available_license(user.id)
                if lic:
                    await binding_svc.bind_license_to_account(
                        lic.license_key, account,
                        telegram_id=tg_user.id,
                    )
                    license_bound = True
            except Exception:
                pass
            await acc_repo.verify(account.id)
            await session.commit()
            msg_key = "LICENSE_BOUND" if license_bound else "NO_LICENSE"
            await query.edit_message_text(
                text=_texts(lang, msg_key),
                parse_mode="HTML",
                reply_markup=activation_keyboard(lang) if license_bound else no_license_keyboard(lang),
            )
            context.user_data.pop("existing_account_id", None)
            return

        # 4. create trading account from wizard
        try:
            account = await acc_repo.create_from_wizard(
                user_id=user.id,
                setup_data=setup_data,
                encrypted_password=encrypted_password,
                account_fingerprint=account_fingerprint,
            )
        except (AccountAlreadyLinkedToUserError, AccountLinkedToAnotherUserError) as e:
            msg = {
                "EN": "❌ This account is already linked.",
                "FR": "❌ Ce compte est déjà lié.",
                "AR": "❌ هذا الحساب مربوط من قبل.",
                "ES": "❌ Esta cuenta ya está vinculada.",
            }.get(lang, "EN")
            if isinstance(e, AccountLinkedToAnotherUserError):
                msg = {
                    "EN": "❌ This account is linked to another user.\nContact support for safe transfer.",
                    "FR": "❌ Ce compte est lié à un autre utilisateur.\nContactez le support.",
                    "AR": "❌ هذا الحساب مرتبط بمستخدم آخر.\nتواصل مع الدعم.",
                    "ES": "❌ Esta cuenta está vinculada a otro usuario.\nContacta al soporte.",
                }.get(lang, "EN")
            await query.edit_message_text(text=msg, parse_mode="HTML")
            return

        # 5. create scan report entry (summary from what we know)
        scan_data = setup_data.get("scan", {})
        await scan_repo.create(
            account_id=account.id,
            broker_detected=scan_data.get("broker_detected"),
            balance_detected=scan_data.get("balance_detected"),
            equity_detected=scan_data.get("equity_detected"),
            leverage_detected=scan_data.get("leverage_detected"),
            symbols_detected=scan_data.get("symbols_detected"),
            mismatches=scan_data.get("mismatches"),
            build=scan_data.get("build"),
            timezone_detected=scan_data.get("timezone_detected"),
            scan_status=scan_data.get("scan_status", "passed"),
        )

        # 6. try to bind an available license
        license_bound = False
        try:
            lic = await binding_svc.find_available_license(user.id)
            if lic:
                await binding_svc.bind_license_to_account(
                    lic.license_key, account,
                    telegram_id=tg_user.id,
                )
                license_bound = True
        except Exception:
            pass

        # 7. mark account verified + commit
        await acc_repo.verify(account.id)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            await query.edit_message_text(
                text={
                    "EN": "❌ This account was just linked by another user.\nContact support if this is your account.",
                    "FR": "❌ Ce compte vient d'être lié par un autre utilisateur.\nContactez le support.",
                    "AR": "❌ هذا الحساب تم ربطه توا من قبل مستخدم آخر.\nتواصل مع الدعم إذا كان هذا حسابك.",
                    "ES": "❌ Esta cuenta fue vinculada por otro usuario.\nContacta al soporte si es tu cuenta.",
                }.get(lang, "EN"),
                parse_mode="HTML",
            )
            return

    # 8. success message
    msg_key = "LICENSE_BOUND" if license_bound else "NO_LICENSE"
    await query.edit_message_text(
        text=_texts(lang, msg_key),
        parse_mode="HTML",
        reply_markup=activation_keyboard(lang) if license_bound else no_license_keyboard(lang),
    )


async def handle_edit_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    context.user_data.clear()

    await query.edit_message_text(
        text="🔄 <b>Restarting setup...</b>\n\nPlease type /start to begin again.",
        parse_mode="HTML",
    )


def _texts(lang: str, key: str) -> str:
    texts = {
        "EN": {
            "LICENSE_BOUND": "✅ <b>Setup Saved & License Bound</b>\n\n"
                             "Your account is linked to an active license.\n\n"
                             "Press <b>Activate Bot</b> to start trading.",
            "NO_LICENSE": "✅ <b>Setup Saved Successfully</b>\n\n"
                          "Your configuration has been saved.\n\n"
                          "❌ <b>No active license found.</b>\n"
                          "Buy or enter a license key to activate trading.",
        },
        "FR": {
            "LICENSE_BOUND": "✅ <b>Configuration enregistrée & licence liée</b>\n\n"
                             "Votre compte est lié à une licence active.\n\n"
                             "Appuyez sur <b>Activer le Bot</b> pour commencer.",
            "NO_LICENSE": "✅ <b>Configuration enregistrée</b>\n\n"
                          "Votre configuration a été sauvegardée.\n\n"
                          "❌ <b>Aucune licence active trouvée.</b>\n"
                          "Achetez ou entrez une clé de licence pour activer le trading.",
        },
        "AR": {
            "LICENSE_BOUND": "✅ <b>تم حفظ الإعداد وربط الترخيص</b>\n\n"
                             "حسابك مرتبط برخصة نشطة.\n\n"
                             "اضغط <b>تشغيل البوت</b> لبدء التداول.",
            "NO_LICENSE": "✅ <b>تم حفظ الإعداد بنجاح</b>\n\n"
                          "تم حفظ إعداداتك.\n\n"
                          "❌ <b>لا توجد رخصة نشطة.</b>\n"
                          "اشترِ أو أدخل مفتاح ترخيص لتفعيل التداول.",
        },
        "ES": {
            "LICENSE_BOUND": "✅ <b>Configuración guardada & licencia vinculada</b>\n\n"
                             "Tu cuenta está vinculada a una licencia activa.\n\n"
                             "Presiona <b>Activar Bot</b> para empezar.",
            "NO_LICENSE": "✅ <b>Configuración guardada correctamente</b>\n\n"
                          "Tu configuración ha sido guardada.\n\n"
                          "❌ <b>No se encontró licencia activa.</b>\n"
                          "Compra o ingresa una clave de licencia para activar el trading.",
        },
    }
    return texts.get(lang, texts["EN"]).get(key, key)


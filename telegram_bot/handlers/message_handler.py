from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import re

import logging

logger = logging.getLogger(__name__)

from telegram_bot.ui.keyboards.trading_modes import trading_modes_keyboard
from telegram_bot.ui.keyboards.mt5 import mt5_warning_keyboard
from telegram_bot.ui.keyboards.confirm import confirm_keyboard
from telegram_bot.services.setup import get_setup
from telegram_bot.services.mt_connector import mt_connector, MTLoginData
from telegram_bot.services.account_verification_service import account_scanner
from telegram_bot.ui.keyboards.retry import retry_keyboard
from security.account_fingerprint import build_account_fingerprint
from database.db import async_session_factory
from datetime import datetime, timezone
from database.models import User
from sqlalchemy import select, func
from database.repositories.account_repository import AccountRepository, AccountAlreadyLinkedToUserError
from database.repositories import UserRepository, LicenseRepository
from telegram_bot.ui.keyboards.account_type import account_type_keyboard
from telegram_bot.ui.keyboards.license_keyboard import no_license_keyboard
from telegram_bot.handlers.callbacks.rename_account import _msg as rename_msg


def get_msg(lang, messages):
    return messages.get(lang, messages["EN"])


def is_valid_domain(text: str):
    raw = text.strip().lower()
    raw = re.sub(r"^https?://", "", raw)
    raw = raw.split("/")[0]
    if len(raw) < 4 or len(raw) > 100:
        return False
    if "." not in raw:
        return False
    if not re.match(r"^[a-z0-9\-\.]+$", raw):
        return False
    return True


def format_amount(value):
    try:
        num = float(value)
        if num >= 1000000:
            return f"{num / 1000000:g}M"
        if num >= 1000:
            return f"{num / 1000:g}K"
        return f"{num:g}"
    except Exception:
        return str(value)


def normalize_funded_size(text: str):
    raw = text.strip().upper().replace(" ", "")

    try:
        if raw.endswith("K"):
            num = float(raw[:-1])
            if num <= 0 or num > 10000:
                return None
            if num >= 1000:
                m = num / 1000
                return f"{int(m) if m.is_integer() else m:g}M"
            return f"{int(num) if num.is_integer() else num:g}K"

        if raw.endswith("M"):
            num = float(raw[:-1])
            if num <= 0 or num > 10:
                return None
            return f"{int(num) if num.is_integer() else num:g}M"

        num = float(raw)
        if num <= 0:
            return None
        if num < 1000:
            return f"{int(num) if num.is_integer() else num:g}K"
        if num <= 10000:
            m = num / 1000
            return f"{int(m) if m.is_integer() else m:g}M"

    except Exception:
        return None

    return None


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    lang = context.user_data.get("language", "EN")
    waiting_for = context.user_data.get("waiting_for")
    setup = get_setup(context)

    if waiting_for == "ACCOUNT_BALANCE":
        raw = text.replace("$", "").replace(",", "").strip()

        try:
            balance = float(raw)
        except Exception:
            await update.message.reply_text(get_msg(lang, {
                "EN": "❌ Please enter a valid balance. Example: 100",
                "FR": "❌ Entrez un solde valide. Exemple: 100",
                "AR": "❌ اكتب رصيد صحيح. مثال: 100",
                "ES": "❌ Escribe un balance válido. Ejemplo: 100",
            }))
            return

        if balance < 20 or balance > 5000:
            await update.message.reply_text(get_msg(lang, {
                "EN": "❌ Balance must be between $20 and $5000.\nRecommended minimum deposit: $100.",
                "FR": "❌ Le solde doit être entre 20$ et 5000$.\nDépôt minimum recommandé : 100$.",
                "AR": "❌ الرصيد يجب ان يكون بين 20$ و 5000$.\nالحد الأدنى المنصوح به هو 100$.",
                "ES": "❌ El balance debe estar entre 20$ y 5000$.\nDepósito mínimo recomendado: 100$.",
            }))
            return

        setup["account"]["balance"] = balance
        setup["account"]["currency"] = "USD"
        context.user_data["account_balance"] = balance
        context.user_data["waiting_for"] = None

        bal_str = f"${int(balance)}" if balance == int(balance) else f"${balance:.2f}"
        await update.message.reply_text(
            text=get_msg(lang, {
                "EN": f"✅ <b>Balance saved</b>\n\nBalance: {bal_str}\n\n⚠️ <b>Security Notice</b>\n\nIf you don't trust the bot yet, connect a demo account first.",
                "FR": f"✅ <b>Solde enregistré</b>\n\nSolde: {bal_str}\n\n⚠️ <b>Avis de sécurité</b>\n\nSi vous ne faites pas encore confiance au bot, connectez d'abord un compte démo.",
                "AR": f"✅ <b>تم حفظ الرصيد</b>\n\nالرصيد: {bal_str}\n\n⚠️ <b>تنبيه أمني</b>\n\nإذا لم تكن واثقاً بالبوت بعد، يرجى ربط حساب تجريبي أولاً.",
                "ES": f"✅ <b>Balance guardado</b>\n\nBalance: {bal_str}\n\n⚠️ <b>Aviso de seguridad</b>\n\nSi aún no confías en el bot, conecta primero una cuenta demo.",
            }),
            parse_mode="HTML",
            reply_markup=mt5_warning_keyboard(),
        )
        return

    if waiting_for == "CUSTOM_BROKER":
        if not is_valid_domain(text):
            await update.message.reply_text(get_msg(lang, {
                "EN": "❌ Enter a valid domain. Example: icmarkets.com, pepperstone.com",
                "FR": "❌ Entrez un domaine valide. Exemple: icmarkets.com, pepperstone.com",
                "AR": "❌ اكتب نطاق صحيح. مثال: icmarkets.com, pepperstone.com",
                "ES": "❌ Ingrese un dominio válido. Ejemplo: icmarkets.com, pepperstone.com",
            }))
            return

        domain = text.strip().lower()
        domain = re.sub(r"^https?://", "", domain)
        domain = domain.split("/")[0]

        setup["broker"]["id"] = "other"
        setup["broker"]["name"] = domain

        context.user_data["broker"] = domain
        context.user_data["waiting_for"] = None

        await update.message.reply_text(
            text=f"✅ <b>Broker saved</b>\n\n{domain}\n\n⚙️ <b>Choose Trading Mode</b>",
            parse_mode="HTML",
            reply_markup=trading_modes_keyboard(),
        )
        return

    if waiting_for == "CUSTOM_PROP_FIRM":
        if not is_valid_domain(text):
            await update.message.reply_text(get_msg(lang, {
                "EN": "❌ Enter a valid domain. Example: ftmo.com, fundednext.com",
                "FR": "❌ Entrez un domaine valide. Exemple: ftmo.com, fundednext.com",
                "AR": "❌ اكتب نطاق صحيح. مثال: ftmo.com, fundednext.com",
                "ES": "❌ Ingrese un dominio válido. Ejemplo: ftmo.com, fundednext.com",
            }))
            return

        domain = text.strip().lower()
        domain = re.sub(r"^https?://", "", domain)
        domain = domain.split("/")[0]

        setup["prop_firm"]["id"] = "other"
        setup["prop_firm"]["name"] = domain

        context.user_data["prop_firm"] = "other"
        context.user_data["prop_firm_name"] = domain
        context.user_data["waiting_for"] = "CUSTOM_DAILY_LOSS"

        await update.message.reply_text(
            text=f"✅ <b>Prop firm saved</b>\n\n{domain}\n\n✍️ Type Daily Loss %. Example: 5",
            parse_mode="HTML",
        )
        return

    if waiting_for == "CUSTOM_DAILY_LOSS":
        try:
            value = float(text.replace("%", "").strip())
        except Exception:
            value = None

        if value is None or value < 0 or value > 10:
            await update.message.reply_text(get_msg(lang, {
                "EN": "❌ Please enter a number between 0 and 10. Example: 5",
                "FR": "❌ Entrez un nombre entre 0 et 10. Exemple: 5",
                "AR": "❌ اكتب رقم بين 0 و 10. مثال: 5",
                "ES": "❌ Escribe un número entre 0 y 10. Ejemplo: 5",
            }))
            return

        setup["risk"]["daily_loss"] = value
        context.user_data["funded_daily_loss"] = value
        context.user_data["waiting_for"] = "CUSTOM_MAX_LOSS"

        await update.message.reply_text("✍️ Type Max Loss %. Example: 10")
        return

    if waiting_for == "CUSTOM_MAX_LOSS":
        try:
            value = float(text.replace("%", "").strip())
        except Exception:
            value = None

        if value is None or value < 0 or value > 10:
            await update.message.reply_text(get_msg(lang, {
                "EN": "❌ Please enter a number between 0 and 10. Example: 5",
                "FR": "❌ Entrez un nombre entre 0 et 10. Exemple: 5",
                "AR": "❌ اكتب رقم بين 0 و 10. مثال: 5",
                "ES": "❌ Escribe un número entre 0 y 10. Ejemplo: 5",
            }))
            return

        setup["risk"]["max_loss"] = value
        context.user_data["funded_max_loss"] = value
        context.user_data["waiting_for"] = "CUSTOM_TARGET"

        await update.message.reply_text("✍️ Type Profit Target %. Example: 8")
        return

    if waiting_for == "CUSTOM_TARGET":
        try:
            value = float(text.replace("%", "").strip())
        except Exception:
            value = None

        if value is None or value < 0 or value > 10:
            await update.message.reply_text(get_msg(lang, {
                "EN": "❌ Please enter a number between 0 and 10. Example: 5",
                "FR": "❌ Entrez un nombre entre 0 et 10. Exemple: 5",
                "AR": "❌ اكتب رقم بين 0 و 10. مثال: 5",
                "ES": "❌ Escribe un número entre 0 y 10. Ejemplo: 5",
            }))
            return

        setup["risk"]["profit_target"] = value
        context.user_data["funded_profit_target"] = value
        context.user_data["waiting_for"] = "CUSTOM_MIN_TRADES"

        await update.message.reply_text("✍️ Type minimum trades/days required. Example: 5")
        return

    if waiting_for == "CUSTOM_MIN_TRADES":
        try:
            value = int(float(text.strip()))
        except Exception:
            value = None

        if value is None or value < 0 or value > 60:
            await update.message.reply_text(get_msg(lang, {
                "EN": "❌ Please enter a reasonable number between 0 and 60. Example: 5",
                "FR": "❌ Entrez un nombre raisonnable entre 0 et 60. Exemple: 5",
                "AR": "❌ اكتب رقم معقول بين 0 و 60. مثال: 5",
                "ES": "❌ Escribe un número razonable entre 0 y 60. Ejemplo: 5",
            }))
            return

        setup["risk"]["min_trades"] = value
        context.user_data["funded_min_trades"] = value
        context.user_data["waiting_for"] = "CUSTOM_FUNDED_SIZE"

        await update.message.reply_text("✍️ Type account size. Example: 100K")
        return

    if waiting_for == "CUSTOM_FUNDED_SIZE":
        size = normalize_funded_size(text)

        if size is None:
            await update.message.reply_text(get_msg(lang, {
                "EN": "❌ Please enter a valid account size. Example: 10K, 100K, 1M",
                "FR": "❌ Entrez une taille valide. Exemple: 10K, 100K, 1M",
                "AR": "❌ اكتب حجم حساب صحيح. مثال: 10K أو 100K أو 1M",
                "ES": "❌ Escribe un tamaño válido. Ejemplo: 10K, 100K, 1M",
            }))
            return

        setup["account"]["balance"] = size
        setup["prop_firm"]["account_size"] = size

        context.user_data["funded_account_size"] = size
        context.user_data["waiting_for"] = None

        await update.message.reply_text(
            text=(
                "✅ <b>Funded rules saved</b>\n\n"
                f"Firm: {context.user_data.get('prop_firm_name')}\n"
                f"Daily Loss: {context.user_data.get('funded_daily_loss')}%\n"
                f"Max Loss: {context.user_data.get('funded_max_loss')}%\n"
                f"Target: {context.user_data.get('funded_profit_target')}%\n"
                f"Min Trades/Days: {context.user_data.get('funded_min_trades')}\n"
                f"Account Size: {size}\n\n"
                "⚙️ <b>Choose Trading Mode</b>"
            ),
            parse_mode="HTML",
            reply_markup=trading_modes_keyboard(),
        )
        return

    if waiting_for == "MT_SERVER":
        raw_server = text.strip()
        if not re.match(r"^[a-zA-Z0-9\-_\.\s]{3,80}$", raw_server) or not re.search(r"[a-zA-Z]", raw_server):
            await update.message.reply_text(get_msg(lang, {
                "EN": "❌ Enter a valid server name. It must contain letters (not just numbers). Example: FundingPips-SIM1",
                "FR": "❌ Entrez un serveur valide. Il doit contenir des lettres (pas que des chiffres). Exemple: FundingPips-SIM1",
                "AR": "❌ اكتب اسم سيرفر صحيح. يجب أن يحتوي على حروف (ليس أرقام فقط). مثال: FundingPips-SIM1",
                "ES": "❌ Ingrese un servidor válido. Debe contener letras (no solo números). Ejemplo: FundingPips-SIM1",
            }))
            return

        setup["platform"]["server"] = raw_server
        context.user_data["mt_server"] = raw_server
        context.user_data["waiting_for"] = "MT_LOGIN"

        await update.message.reply_text(
            text=get_msg(lang, {
                "EN": "🔢 <b>Login ID</b>\n\nPlease enter your account login number.\n\nExample:\n12345678",
                "FR": "🔢 <b>Login ID</b>\n\nVeuillez entrer le numéro de login du compte.\n\nExemple :\n12345678",
                "AR": "🔢 <b>رقم الدخول</b>\n\nاكتب رقم الدخول ديال الحساب.\n\nمثال:\n12345678",
                "ES": "🔢 <b>Login ID</b>\n\nEscribe el número de login de la cuenta.\n\nEjemplo:\n12345678",
            }),
            parse_mode="HTML",
        )
        return

    if waiting_for == "MT_LOGIN":
        if not text.isdigit() or len(text) < 5 or len(text) > 12:
            await update.message.reply_text(get_msg(lang, {
                "EN": "❌ Login ID must be numbers only, usually 5 to 12 digits.\nExample: 12345678",
                "FR": "❌ Le Login ID doit contenir uniquement des chiffres, généralement 5 à 12 chiffres.\nExemple: 12345678",
                "AR": "❌ رقم الدخول يجب ان يكون أرقام فقط، غالباً بين 5 و 12 رقم.\nمثال: 12345678",
                "ES": "❌ El Login ID debe contener solo números, normalmente entre 5 y 12 dígitos.\nEjemplo: 12345678",
            }))
            return

        setup["platform"]["login"] = text
        context.user_data["mt_login"] = text
        context.user_data["waiting_for"] = "MT_PASSWORD"

        platform = setup["platform"].get("type") or context.user_data.get("platform", "MT5")

        await update.message.reply_text(
            text=get_msg(lang, {
                "EN": f"🔑 <b>{platform} Password</b>\n\nPlease enter your {platform} password.",
                "FR": f"🔑 <b>Mot de passe {platform}</b>\n\nVeuillez entrer votre mot de passe {platform}.",
                "AR": f"🔑 <b>كلمة مرور {platform}</b>\n\nاكتب كلمة مرور {platform}.",
                "ES": f"🔑 <b>Contraseña {platform}</b>\n\nEscribe tu contraseña de {platform}.",
            }),
            parse_mode="HTML",
        )
        return

    if waiting_for == "MT_PASSWORD":
        setup["platform"]["password"] = text
        context.user_data["mt_password"] = text
        context.user_data["waiting_for"] = None

        # Clear previous scan data before new scan
        setup.pop("scan", None)
        context.user_data.pop("encrypted_password", None)

        login_data = MTLoginData(
            platform=setup["platform"].get("type") or context.user_data.get("platform", "MT5"),
            server=setup["platform"].get("server") or context.user_data.get("mt_server"),
            login=setup["platform"].get("login") or context.user_data.get("mt_login"),
            password=setup["platform"].get("password") or context.user_data.get("mt_password"),
        )

        result = await mt_connector.test_connection(login_data)

        report = await account_scanner.run_full_scan(
            login_data=login_data,
            scan_result=result,
            setup_data=setup,
            user_data=context.user_data,
        )

        report_parts = account_scanner.format_report(report, setup, lang)

        # store scan summary for DB when user confirms
        if report.account and report.connection.success:
            context.user_data["encrypted_password"] = context.user_data.get("mt_password", "")
            syms = ",".join(
                m.broker_symbol or m.market
                for m in (report.markets or [])
            ) if report.markets else None
            symbol_mapping = {
                m.market: m.broker_symbol
                for m in (report.markets or [])
                if m.found and m.broker_symbol
            }
            mm_text = None
            if report.comparison and report.comparison.items:
                mm_parts = []
                for v in report.comparison.items:
                    if v.status != "match":
                        mm_parts.append(f"{v.field}:{v.expected}vs{v.actual}")
                mm_text = "; ".join(mm_parts) if mm_parts else None
            context.user_data.setdefault("setup", {})["scan"] = {
                "broker_detected": report.account.broker,
                "balance_detected": report.account.balance,
                "equity_detected": report.account.equity,
                "leverage_detected": report.account.leverage,
                "symbols_detected": syms,
                "symbol_mapping": symbol_mapping,
                "mismatches": mm_text,
                "build": report.account.build,
                "timezone_detected": report.account.timezone,
                "scan_status": "passed" if report.connection.success else "failed",
            }

        scan_msg = await update.message.reply_text(
            text="\n\n".join(report_parts),
            parse_mode="HTML",
        )
        context.user_data["scan_message_id"] = scan_msg.message_id

        if not report.connection.success:
            await update.message.reply_text(
                text=get_msg(lang, {
                    "EN": "What would you like to do?",
                    "FR": "Que voulez-vous faire ?",
                    "AR": "ماذا تريد أن تفعل؟",
                    "ES": "¿Qué quieres hacer?",
                }),
                reply_markup=retry_keyboard(lang),
            )
            return

        # Build fingerprint and check for existing binding
        platform = setup["platform"].get("type") or context.user_data.get("platform", "MT5")
        server = setup["platform"].get("server") or context.user_data.get("mt_server")
        login = setup["platform"].get("login") or context.user_data.get("mt_login")
        fingerprint = build_account_fingerprint(platform=platform, server=server, login=login)
        context.user_data["account_fingerprint"] = fingerprint

        async with async_session_factory() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == update.effective_user.id)
            )
            user = result.scalar_one_or_none()
            uid = user.id if user else None

            acc_repo = AccountRepository(session)
            existing = await acc_repo.get_bound_by_fingerprint(fingerprint)

            if existing:
                if uid and existing.user_id == uid and existing.license_id is not None:
                    await update.message.reply_text(
                        text=get_msg(lang, {
                            "EN": "ℹ️ This account is already linked to your account.\n\nYou can manage it from 'My Accounts', or remove it and link again.",
                            "FR": "ℹ️ Ce compte est déjà lié à votre compte.\n\nVous pouvez le gérer depuis 'Mes Comptes', ou le supprimer et le lier à nouveau.",
                            "AR": "ℹ️ هذا الحساب مربوط بحسابك من قبل.\n\nيمكنك إدارته من قسم 'حساباتي'، أو حذفه ثم ربطه من جديد.",
                            "ES": "ℹ️ Esta cuenta ya está vinculada a tu cuenta.\n\nPuedes gestionarla desde 'Mis Cuentas', o eliminarla y vincularla de nuevo.",
                        }),
                        parse_mode="HTML",
                    )
                    return
                if not uid or existing.user_id != uid:
                    await update.message.reply_text(
                        text=get_msg(lang, {
                            "EN": "❌ Cannot link this account.\n\nThis MT4/MT5 account is linked to another user.\nIf this account is yours, contact support for safe transfer.",
                            "FR": "❌ Impossible de lier ce compte.\n\nCe compte MT4/MT5 est lié à un autre utilisateur.\nSi ce compte vous appartient, contactez le support.",
                            "AR": "❌ لا يمكن ربط هذا الحساب.\n\nحساب MT4/MT5 هذا مرتبط بمستخدم آخر.\nإذا كان الحساب ملكك، تواصل مع الدعم لنقل الربط بشكل آمن.",
                            "ES": "❌ No se puede vincular esta cuenta.\n\nEsta cuenta MT4/MT5 está vinculada a otro usuario.\nSi esta cuenta es tuya, contacta al soporte para transferirla.",
                        }),
                        parse_mode="HTML",
                    )
                    return

                # same user, no license → proceed to confirm (will bind license)
                context.user_data["existing_account_id"] = existing.id

        context.user_data["waiting_for"] = None
        confirm_msg = await update.message.reply_text(
            text=get_msg(lang, {
                "EN": "✅ <b>Review Complete</b>\n\nEverything looks good.\n\nDo you want to save this configuration?",
                "FR": "✅ <b>Vérification terminée</b>\n\nTout semble correct.\n\nVoulez-vous sauvegarder cette configuration ?",
                "AR": "✅ <b>اكتملت المراجعة</b>\n\nكل شيء يبدو جيداً.\n\nهل تريد حفظ هذا الإعداد؟",
                "ES": "✅ <b>Revisión completa</b>\n\nTodo parece correcto.\n\n¿Quieres guardar esta configuración?",
            }),
            parse_mode="HTML",
            reply_markup=confirm_keyboard(lang),
        )
        context.user_data["confirm_message_id"] = confirm_msg.message_id
        return

    if waiting_for == "LICENSE_KEY":
        async with async_session_factory() as session:
            user_repo = UserRepository(session)
            lic_repo = LicenseRepository(session)
            user = await user_repo.get_by_telegram_id(update.effective_user.id)
            if not user:
                await update.message.reply_text("❌ User not found. Use /start")
                return

            lic = await lic_repo.get_by_key(text.strip())
            if not lic:
                await update.message.reply_text(get_msg(lang, {
                    "EN": "❌ Invalid license key. Please try again.",
                    "FR": "❌ Clé de licence invalide. Veuillez réessayer.",
                    "AR": "❌ مفتاح الترخيص غير صحيح. حاول مرة أخرى.",
                    "ES": "❌ Clave de licencia inválida. Intenta de nuevo.",
                }), reply_markup=no_license_keyboard(lang))
                return

            if lic.status != "active":
                await update.message.reply_text(get_msg(lang, {
                    "EN": "❌ This license is not active.",
                    "FR": "❌ Cette licence n'est pas active.",
                    "AR": "❌ هذه الرخصة غير نشطة.",
                    "ES": "❌ Esta licencia no está activa.",
                }), reply_markup=no_license_keyboard(lang))
                return

            tg_id = update.effective_user.id
            if lic.telegram_id is None:
                lic.telegram_id = tg_id
                lic.bound_at = datetime.now(timezone.utc)
                if lic.user_id != user.id:
                    lic.user_id = user.id
                await session.commit()
            elif lic.telegram_id != tg_id:
                await update.message.reply_text(get_msg(lang, {
                    "EN": "❌ This license is bound to another account.\nContact support if you want to transfer it.",
                    "FR": "❌ Cette licence est liée à un autre compte.\nContactez le support pour la transférer.",
                    "AR": "❌ هذا الترخيص مرتبط بحساب آخر.\nتواصل مع الدعم إذا كنت تريد نقل الترخيص.",
                    "ES": "❌ Esta licencia está vinculada a otra cuenta.\nContacta al soporte para transferirla.",
                }), reply_markup=no_license_keyboard(lang))
                return

            await lic_repo.activate(lic.id)
            await session.commit()

        context.user_data["waiting_for"] = None
        await update.message.reply_text(
            text=get_msg(lang, {
                "EN": "✅ <b>License Activated</b>\n\nYour license is now active. Choose your account type.",
                "FR": "✅ <b>Licence activée</b>\n\nVotre licence est maintenant active. Choisissez le type de compte.",
                "AR": "✅ <b>تم تفعيل الترخيص</b>\n\nرخصتك نشطة الآن. اختر نوع الحساب.",
                "ES": "✅ <b>Licencia activada</b>\n\nTu licencia ahora está activa. Selecciona el tipo de cuenta.",
            }),
            parse_mode="HTML",
            reply_markup=account_type_keyboard(lang),
        )
        return

    if waiting_for == "TICKET_REPLY":
        reply_text = text.strip()
        if len(reply_text) < 1 or len(reply_text) > 5000:
            await update.message.reply_text(get_msg(lang, {
                "EN": "❌ Message must be between 1 and 5000 characters.",
                "AR": "❌ الرسالة يجب أن تكون بين 1 و 5000 حرف.",
                "FR": "❌ Le message doit comporter entre 1 et 5000 caractères.",
                "ES": "❌ El mensaje debe tener entre 1 y 5000 caracteres.",
            }))
            return

        ticket_id = context.user_data.get("ticket_reply_id")
        context.user_data.pop("ticket_reply_id", None)
        context.user_data["waiting_for"] = None

        if not ticket_id:
            await update.message.reply_text("❌ No ticket selected. Open a ticket first.")
            return

        try:
            from telegram_bot.services.support_service import get_my_ticket, reply_to_my_ticket

            async with async_session_factory() as session:
                user_repo = UserRepository(session)
                user = await user_repo.get_by_telegram_id(update.effective_user.id)
                if not user:
                    await update.message.reply_text("❌ User not found. Use /start first.")
                    return
                ticket = await get_my_ticket(session, user.id, ticket_id)
                if not ticket:
                    await update.message.reply_text("❌ Ticket not found.")
                    return
                if ticket.status == "closed":
                    await update.message.reply_text(get_msg(lang, {
                        "EN": "❌ This ticket is closed. Create a new ticket for further help.",
                        "AR": "❌ هذه التذكرة مغلقة. أنشئ تذكرة جديدة لمزيد من المساعدة.",
                        "FR": "❌ Ce ticket est fermé. Créez un nouveau ticket pour obtenir de l'aide.",
                        "ES": "❌ Este ticket está cerrado. Crea un nuevo ticket para obtener ayuda.",
                    }))
                    return
                await reply_to_my_ticket(session, ticket, user, reply_text)
                ticket_number = ticket.ticket_number
        except Exception as e:
            logger.exception("Failed to reply to ticket")
            await update.message.reply_text(get_msg(lang, {
                "EN": "❌ Failed to send your reply. Please try again.",
                "AR": "❌ فشل إرسال ردك. حاول مرة أخرى.",
                "FR": "❌ Échec de l'envoi de votre réponse. Réessayez.",
                "ES": "❌ Error al enviar tu respuesta. Intenta de nuevo.",
            }))
            return

        await update.message.reply_text(
            text=get_msg(lang, {
                "EN": (
                    f"✅ <b>Reply Added</b>\n\n"
                    f"Ticket: <b>{ticket_number}</b>\n\n"
                    f"Your reply was added to the conversation."
                ),
                "AR": (
                    f"✅ <b>تمت إضافة الرد</b>\n\n"
                    f"التذكرة: <b>{ticket_number}</b>\n\n"
                    f"تمت إضافة ردك إلى المحادثة."
                ),
                "FR": (
                    f"✅ <b>Réponse ajoutée</b>\n\n"
                    f"Ticket: <b>{ticket_number}</b>\n\n"
                    f"Votre réponse a été ajoutée à la conversation."
                ),
                "ES": (
                    f"✅ <b>Respuesta añadida</b>\n\n"
                    f"Ticket: <b>{ticket_number}</b>\n\n"
                    f"Tu respuesta se añadió a la conversación."
                ),
            }),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    {"EN": "🎫 My Tickets", "AR": "🎫 تذاكري", "FR": "🎫 Mes Tickets", "ES": "🎫 Mis Tickets"}
                    .get(lang, "🎫 My Tickets"),
                    callback_data="TICKET:LIST"
                )
            ]]),
        )
        return

    if waiting_for == "TICKET_OTHER_CAT":
        category = text.strip()
        if len(category) < 2 or len(category) > 50:
            await update.message.reply_text(get_msg(lang, {
                "EN": "❌ Category must be between 2 and 50 characters.",
                "AR": "❌ الفئة يجب أن تكون بين 2 و 50 حرف.",
                "FR": "❌ La catégorie doit comporter entre 2 et 50 caractères.",
                "ES": "❌ La categoría debe tener entre 2 y 50 caracteres.",
            }))
            return
        context.user_data["ticket_category"] = category
        context.user_data["waiting_for"] = "TICKET_DESCRIPTION"
        await update.message.reply_text(
            text=get_msg(lang, {
                "EN": f"✍️ <b>Describe your issue</b>\n\nCategory: <b>{category}</b>\n\nPlease describe the problem in detail.",
                "AR": f"✍️ <b>صِف مشكلتك</b>\n\nالفئة: <b>{category}</b>\n\nصِف المشكلة بالتفصيل.",
                "FR": f"✍️ <b>Décrivez votre problème</b>\n\nCatégorie: <b>{category}</b>\n\nDécrivez le problème en détail.",
                "ES": f"✍️ <b>Describe tu problema</b>\n\nCategoría: <b>{category}</b>\n\nDescribe el problema en detalle.",
            }),
            parse_mode="HTML",
        )
        return

    if waiting_for == "TICKET_DESCRIPTION":
        description = text.strip()
        if len(description) < 10:
            await update.message.reply_text(get_msg(lang, {
                "EN": "❌ Description must be at least 10 characters.",
                "AR": "❌ الوصف يجب أن يكون على الأقل 10 حروف.",
                "FR": "❌ La description doit comporter au moins 10 caractères.",
                "ES": "❌ La descripción debe tener al menos 10 caracteres.",
            }))
            return

        category = context.user_data.get("ticket_category", "other")
        context.user_data.pop("ticket_category", None)
        context.user_data["waiting_for"] = None

        try:
            from telegram_bot.services.support_service import create_ticket_for_telegram

            async with async_session_factory() as session:
                user_repo = UserRepository(session)
                user = await user_repo.get_by_telegram_id(update.effective_user.id)

                if not user:
                    await update.message.reply_text("❌ User not found. Use /start first.")
                    return

                # Shared service: race-free numbering, opening message, audit,
                # support-inbox email. Same records the dashboards read.
                ticket = await create_ticket_for_telegram(
                    session,
                    user=user,
                    category=category,
                    description=description,
                    client_ref=f"{user.first_name or ''} {user.last_name or ''}".strip()
                    + f" (telegram @{update.effective_user.username or update.effective_user.id})",
                )
                ticket_number = ticket.ticket_number

                await update.message.reply_text(
                    text=get_msg(lang, {
                        "EN": (
                            f"✅ <b>Ticket Created</b>\n\n"
                            f"Ticket: <b>{ticket_number}</b>\n"
                            f"Category: {category}\n\n"
                            f"We will respond within 24h."
                        ),
                        "AR": (
                            f"✅ <b>تم إنشاء التذكرة</b>\n\n"
                            f"التذكرة: <b>{ticket_number}</b>\n"
                            f"الفئة: {category}\n\n"
                            f"سوف نرد خلال 24 ساعة."
                        ),
                        "FR": (
                            f"✅ <b>Ticket Créé</b>\n\n"
                            f"Ticket: <b>{ticket_number}</b>\n"
                            f"Catégorie: {category}\n\n"
                            f"Nous répondrons sous 24h."
                        ),
                        "ES": (
                            f"✅ <b>Ticket Creado</b>\n\n"
                            f"Ticket: <b>{ticket_number}</b>\n"
                            f"Categoría: {category}\n\n"
                            f"Responderemos dentro de 24h."
                        ),
                    }),
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton(
                            {"EN": "🏠 Main Menu", "AR": "🏠 القائمة الرئيسية", "FR": "🏠 Menu Principal", "ES": "🏠 Menú Principal"}
                            .get(lang, "🏠 Main Menu"),
                            callback_data="MENU:MAIN"
                        )
                    ]]),
                )

        except Exception as e:
            logger.exception("Failed to create ticket")
            await update.message.reply_text(get_msg(lang, {
                "EN": "❌ Failed to create ticket. Please try again or contact support@ictfunded.com",
                "AR": "❌ فشل في إنشاء التذكرة. حاول مرة أخرى أو تواصل مع support@ictfunded.com",
                "FR": "❌ Échec de création du ticket. Réessayez ou contactez support@ictfunded.com",
                "ES": "❌ Error al crear el ticket. Intenta de nuevo o contacta support@ictfunded.com",
            }))
        return

    if waiting_for == "ACCOUNT_RENAME":
        name = text.strip()
        if len(name) > 60:
            await update.message.reply_text(rename_msg(lang, "TOO_LONG"))
            return
        if not name:
            await update.message.reply_text(rename_msg(lang, "EMPTY"))
            return

        account_id = context.user_data.get("rename_account_id")
        if not account_id:
            await update.message.reply_text("❌ Session expired. Please go to My Accounts.")
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

            account.name = name
            await session.commit()

        context.user_data["waiting_for"] = None
        context.user_data.pop("rename_account_id", None)

        await update.message.reply_text(
            rename_msg(lang, "SUCCESS").format(name=name),
            parse_mode="HTML",
        )
        return

    await update.message.reply_text(get_msg(lang, {
        "EN": "Please use the menu buttons.",
        "FR": "Veuillez utiliser les boutons du menu.",
        "AR": "استعمل أزرار القائمة من فضلك.",
        "ES": "Usa los botones del menú.",
    }))
"""/bind <CODE> — secure Telegram linking for the dashboard Connect flow.

The dashboard issues a short-lived code (stored hashed in the user's
`preferences.telegram_bind`). The user sends it to the bot; this handler
resolves the real Telegram user id (the stable identifier) and links it to
the platform account that owns the code. The username is stored as
display-only secondary information.

Security:
- The code is single-use and expires (dashboard issues a new one each time).
- Only a code hash is stored server-side; the plaintext code travels once
  from dashboard to bot.
- A Telegram user can only ever be linked to the account that issued the
  code — there is no way to claim an arbitrary chat id.
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone

from sqlalchemy import select

from database.db import async_session_factory
from database.models import User
from security.audit import log_event

logger = logging.getLogger(__name__)


async def bind_command(update, context):
    args = context.args or []
    code = (args[0] if args else "").strip().upper()
    if not code:
        await update.message.reply_text(
            _msg(context.user_data.get("language", "EN"), "USAGE")
        )
        return

    tg_user = update.effective_user
    now = datetime.now(timezone.utc)
    target = None

    async with async_session_factory() as session:
        result = await session.execute(
            select(User).where(User.preferences["telegram_bind"].astext != "null")
        )
        for user in result.scalars().all():
            bind = (user.preferences or {}).get("telegram_bind") or {}
            stored_hash = bind.get("code_hash") or ""
            if not stored_hash:
                continue
            if not secrets.compare_digest(stored_hash, _hash_code(code)):
                continue
            try:
                expires = datetime.fromisoformat(bind.get("expires_at", ""))
            except (TypeError, ValueError):
                continue
            if expires <= now:
                continue
            target = user
            break

        if target is None:
            await update.message.reply_text(
                _msg(context.user_data.get("language", "EN"), "INVALID")
            )
            return

        was_connected = target.telegram_id is not None
        target.telegram_id = tg_user.id
        target.telegram_username = (tg_user.username or "")[:120] or None
        prefs = dict(target.preferences or {})
        prefs.pop("telegram_bind", None)
        target.preferences = prefs

        await log_event(
            session,
            "telegram.connected",
            "Telegram user bound to platform account via /bind",
            user_id=target.id,
            payload={"telegram_id": tg_user.id, "was_connected": was_connected},
        )
        await session.commit()

    await update.message.reply_text(
        _msg(context.user_data.get("language", "EN"), "OK").format(
            username="@" + (tg_user.username or str(tg_user.id)),
            telegram_id=tg_user.id,
        ),
        parse_mode="HTML",
    )
    logger.info("Telegram account linked via /bind (user=%s)", target.id)


def _hash_code(code: str) -> str:
    import hashlib
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _msg(lang: str, key: str) -> str:
    msgs = {
        "USAGE": {
            "EN": "Usage: /bind <CODE>\n\nSend the 8-character code shown in your dashboard to link this Telegram account.",
            "FR": "Utilisation : /bind <CODE>\n\nEnvoyez le code à 8 caractères affiché dans votre tableau de bord pour lier ce compte Telegram.",
            "AR": "الاستخدام: /bind <CODE>\n\nأرسل الرمز المكوّن من 8 أحرف الظاهر في لوحة التحكم لربط حساب تيليجرام هذا.",
            "ES": "Uso: /bind <CODE>\n\nEnvía el código de 8 caracteres mostrado en tu panel para vincular esta cuenta de Telegram.",
        },
        "INVALID": {
            "EN": "That code is invalid or expired. Open your dashboard → Telegram → Connect to generate a new one.",
            "FR": "Ce code est invalide ou a expiré. Ouvrez votre tableau de bord → Telegram → Connecter pour en générer un nouveau.",
            "AR": "هذا الرمز غير صالح أو منتهي الصلاحية. افتح لوحة التحكم ← تيليجرام ← اتصال لإنشاء رمز جديد.",
            "ES": "Ese código no es válido o ha caducado. Abre tu panel → Telegram → Conectar para generar uno nuevo.",
        },
        "OK": {
            "EN": "✅ <b>Telegram connected</b>\n\nAccount: {username}\nTelegram ID: <code>{telegram_id}</code>\n\nYou will now receive alerts here. Manage preferences from your dashboard.",
            "FR": "✅ <b>Telegram connecté</b>\n\nCompte : {username}\nID Telegram : <code>{telegram_id}</code>\n\nVous recevrez désormais les alertes ici. Gérez vos préférences depuis votre tableau de bord.",
            "AR": "✅ <b>تم ربط تيليجرام</b>\n\nالحساب: {username}\nمعرف تيليجرام: <code>{telegram_id}</code>\n\nستستقبل التنبيهات هنا الآن. إدارة التفضيلات من لوحة التحكم.",
            "ES": "✅ <b>Telegram conectado</b>\n\nCuenta: {username}\nID de Telegram: <code>{telegram_id}</code>\n\nAhora recibirás alertas aquí. Gestiona preferencias desde tu panel.",
        },
    }
    return msgs.get(key, {}).get(lang, msgs.get(key, {}).get("EN", key))

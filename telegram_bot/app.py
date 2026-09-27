"""Single Telegram Application factory — the ONLY place that builds a PTB app.

Rationale (Phase 6.0 — single entrypoint):
- `telegram_bot/bot.py` is the production entrypoint: it polls and starts the
  AlertService (full handler set + alert post_init).
- `telegram_bot/api_client.py` is a send-only client used by the API to push
  messages (start-only handlers, no polling, no alert post_init).

Both share this factory so there is never a second ApplicationBuilder with a
divergent handler set. Handler modules are imported lazily so the API process
does not pull the trading stack when it only wants a send client.
"""
from __future__ import annotations

import asyncio
import logging

from telegram.ext import Application, ApplicationBuilder, CommandHandler
from telegram.ext import CallbackQueryHandler, MessageHandler, filters

logger = logging.getLogger(__name__)


async def _error_handler(update: object, context) -> None:
    logger.error("Unhandled error: %s", context.error, exc_info=context.error)


async def _post_init(app: Application) -> None:
    """Production post_init — start the EventNotificationBridge on the core EventBus.

    The bridge routes every trading event through the full NotificationDispatcher
    pipeline (rules → channels → templates → delivery → audit) with per-user
    preference enforcement.  It replaces the legacy AlertService which had no
    preference gating or audit logging.
    """
    from api.services.notifications.event_bridge import event_notification_bridge

    event_notification_bridge.start()
    app.bot_data["event_bridge"] = event_notification_bridge
    logger.info("EventNotificationBridge started — events routed through NotificationDispatcher")


async def _post_shutdown(app: Application) -> None:
    bridge = app.bot_data.get("event_bridge")
    if bridge is not None:
        try:
            bridge.stop()
            logger.info("EventNotificationBridge stopped")
        except Exception as e:
            logger.warning("Failed to stop EventNotificationBridge: %s", e)

    from database.db import close_db
    try:
        await close_db()
    except Exception as e:
        logger.warning("Error during shutdown: %s", e)
    for t in asyncio.all_tasks():
        if t is not asyncio.current_task() and not t.done():
            t.cancel()
    await asyncio.sleep(0.1)
    print("Shutdown complete.")


def register_handlers(app: Application, *, full: bool = True) -> None:
    """Register handlers. `full=False` registers only /start (send-client use)."""
    from telegram_bot.handlers.start import start_handler

    app.add_handler(CommandHandler("start", start_handler))
    if not full:
        return

    from telegram_bot.handlers.callback_handler import callback_handler
    from telegram_bot.handlers.message_handler import message_handler
    from telegram_bot.commands.debug_smoke import debug_smoke
    from telegram_bot.commands.help_cmd import help_command
    from telegram_bot.commands.history import history_command
    from telegram_bot.commands.license_cmd import license_command
    from telegram_bot.commands.open_trades import open_command
    from telegram_bot.commands.performance import performance_command
    from telegram_bot.commands.validation import (
        validation_status_command,
        validation_summary_command,
    )

    app.add_handler(CommandHandler("debug_smoke", debug_smoke))
    app.add_handler(CommandHandler("debug", debug_smoke))
    app.add_handler(CommandHandler("help_cmd", help_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("history", history_command))
    app.add_handler(CommandHandler("license_cmd", license_command))
    app.add_handler(CommandHandler("license", license_command))
    app.add_handler(CommandHandler("open_trades", open_command))
    app.add_handler(CommandHandler("open", open_command))
    app.add_handler(CommandHandler("performance", performance_command))
    app.add_handler(CommandHandler("validation", validation_status_command))
    app.add_handler(CommandHandler("status", validation_status_command))
    app.add_handler(CommandHandler("summary", validation_summary_command))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))


def build_application(*, full: bool = True, with_alert_post_init: bool = False) -> Application:
    """Build the PTB Application. Raises ValueError when no token is configured."""
    from config.settings import TELEGRAM_BOT_TOKEN

    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is missing")

    builder = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN)
    if with_alert_post_init:
        builder = builder.post_init(_post_init).post_shutdown(_post_shutdown)
    app = builder.build()
    app.add_error_handler(_error_handler)
    register_handlers(app, full=full)
    return app

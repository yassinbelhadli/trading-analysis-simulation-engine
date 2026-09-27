"""Telegram Bot entry point — wires handlers + EventNotificationBridge + trading services.

Pipeline:
    Detection/Execution events → EventBus → EventNotificationBridge → NotificationDispatcher → Telegram
    User commands → Handler → Service → Reply

The Application is built by `telegram_bot.app.build_application` — the single
source of truth for handler registration (Phase 6.0 single-entrypoint fix).
"""
from __future__ import annotations

import logging

from telegram_bot.app import build_application

logger = logging.getLogger(__name__)


def run() -> None:
    print("=" * 60)
    print("ICT Funded EA Pro Telegram Bot Started")
    print("=" * 60)
    app = build_application(full=True, with_alert_post_init=True)
    app.run_polling()


if __name__ == "__main__":
    run()

from telegram.ext import Application

from config.settings import TELEGRAM_BOT_TOKEN
from telegram_bot.app import build_application


class TelegramApplication:
    """Send-only Telegram client for the API process.

    Uses the shared `build_application` factory (start-only handler set, no
    polling, no AlertService). Never calls `run_polling` here — that is the
    sole responsibility of `telegram_bot.bot` (single-entrypoint rule).
    """

    def __init__(self):
        if not TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN is missing")
        self.app: Application = build_application(full=False, with_alert_post_init=False)


telegram_application = TelegramApplication()


if __name__ == "__main__":
    print("api_client is a send-only client — start the bot via telegram_bot/bot.py")

"""Send chart images to Telegram."""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from telegram import Bot
    _TG_AVAILABLE = True
except ImportError:
    _TG_AVAILABLE = False

_DEFAULT_CHAT_ID = 7320801946


def _get_bot() -> Optional[Bot]:
    """Get Telegram bot instance from env."""
    if not _TG_AVAILABLE:
        logger.error("telegram package not installed")
        return None
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not set")
        return None
    return Bot(token=token)


def send_chart(image_path: str,
               caption: str = "",
               chat_id: int = _DEFAULT_CHAT_ID) -> bool:
    """Send a chart image to Telegram synchronously (uses asyncio internally)."""
    import asyncio

    bot = _get_bot()
    if not bot or not os.path.exists(image_path):
        return False

    async def _send():
        with open(image_path, "rb") as f:
            await bot.send_photo(chat_id=chat_id, photo=f, caption=caption)

    try:
        asyncio.run(_send())
        logger.info("Sent chart to chat %s: %s", chat_id, image_path)
        return True
    except Exception as e:
        logger.error("Send failed: %s", e)
        return False


async def send_chart_async(image_path: str,
                           caption: str = "",
                           chat_id: int = _DEFAULT_CHAT_ID) -> bool:
    """Send a chart image to Telegram asynchronously."""
    bot = _get_bot()
    if not bot or not os.path.exists(image_path):
        return False
    try:
        with open(image_path, "rb") as f:
            await bot.send_photo(chat_id=chat_id, photo=f, caption=caption)
        logger.info("Sent chart to chat %s: %s", chat_id, image_path)
        return True
    except Exception as e:
        logger.error("Send failed: %s", e)
        return False


def send_text(text: str, chat_id: int = _DEFAULT_CHAT_ID) -> bool:
    """Send a text message to Telegram."""
    import asyncio
    bot = _get_bot()
    if not bot:
        return False

    async def _send():
        await bot.send_message(chat_id=chat_id, text=text)

    try:
        asyncio.run(_send())
        return True
    except Exception:
        return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    send_text("Dashboard module test")

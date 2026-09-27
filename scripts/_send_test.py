"""Send final chart test to Telegram."""
import sys, os, asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from telegram import Bot
from config.settings import TELEGRAM_BOT_TOKEN

CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID", "7320801946"))

async def main():
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    with open("tv_final.png", "rb") as f:
        await bot.send_photo(chat_id=CHAT_ID, photo=f, caption="<b>Gold M5</b> | clean chart test (no volume, no logo)", parse_mode="HTML")
    print("Sent tv_final.png")

asyncio.run(main())

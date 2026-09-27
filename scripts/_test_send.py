"""Single test send to verify chart quality."""
import sys, os, asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime, timezone
from playwright.async_api import async_playwright
from PIL import Image, ImageDraw, ImageFont
from telegram import Bot
from telegram.constants import ParseMode
from config.settings import TELEGRAM_BOT_TOKEN

CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID", "7320801946"))

_SMALL = None
for fn in ["Segoe UI", "Arial", "DejaVuSans"]:
    try:
        _SMALL = ImageFont.truetype(fn, 9)
        break
    except:
        continue
if not _SMALL: _SMALL = ImageFont.load_default()

async def send_one():
    url = (
        "https://s.tradingview.com/widgetembed/"
        "?symbol=OANDA:XAUUSD&interval=5"
        "&hidesidetoolbar=1&theme=light&style=1"
        "&timezone=Etc/UTC&withfooter=0&hideideas=1&noStudies=true"
    )
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1100, "height": 700})
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(6000)
        raw = await page.screenshot(clip={"x": 0, "y": 40, "width": 1100, "height": 660})
        await browser.close()

    img = Image.open(io.BytesIO(raw)).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0,0,0,0))
    draw = ImageDraw.Draw(overlay)
    draw.text((8, img.height - 14), f"ICT EA PRO | {datetime.now(timezone.utc).strftime('%H:%M UTC')}",
              fill=(120,120,120,80), font=_SMALL, anchor="lt")
    result = Image.alpha_composite(img, overlay)
    buf = io.BytesIO()
    result.save(buf, format="PNG")
    buf.seek(0)

    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    await bot.send_photo(chat_id=CHAT_ID, photo=buf, caption="<b>Gold</b> M5 | no header | no MACD",
                         parse_mode=ParseMode.HTML)
    print("Sent!")

import io
asyncio.run(send_one())

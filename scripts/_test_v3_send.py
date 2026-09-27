"""Send test with final logic — control bar removed, time scale kept, no logo."""
import sys, os, asyncio, io
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

HIDE_JS = """
    () => {
        document.querySelectorAll('div, span, button, svg, canvas').forEach(el => {
            const r = el.getBoundingClientRect();
            const cls = (el.className || '').toString();
            if (r.y > 38 && r.y < 82 && r.width < 500 && r.height < 80) {
                el.style.setProperty('display', 'none', 'important');
            }
            if (cls.includes('control-bar')) {
                el.style.setProperty('display', 'none', 'important');
            }
            if (r.x >= 1029 && r.y >= 660) {
                el.style.setProperty('display', 'none', 'important');
            }
        });
    }
"""

async def send():
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    for sym, tv_sym, name in [
        ("XAUUSD", "OANDA:XAUUSD", "Gold"),
        ("US100.cash", "CAPITALCOM:US100", "Nasdaq"),
        ("BTCUSD", "COINBASE:BTCUSD", "Bitcoin"),
    ]:
        url = (
            "https://s.tradingview.com/widgetembed/"
            f"?symbol={tv_sym}&interval=5"
            "&hidesidetoolbar=1&theme=light&style=1"
            "&timezone=Etc/UTC&withfooter=0&hideideas=1&noStudies=true"
        )
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": 1100, "height": 700})
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(5000)
            await page.evaluate(HIDE_JS)
            await page.wait_for_timeout(500)
            raw = await page.screenshot(
                clip={"x": 0, "y": 38, "width": 1100, "height": 662}
            )
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

        await bot.send_photo(chat_id=CHAT_ID, photo=buf,
                             caption=f"<b>{name}</b> M5 | control bar removed | time scale back | no logo",
                             parse_mode=ParseMode.HTML)
        print(f"Sent {name}")

asyncio.run(send())

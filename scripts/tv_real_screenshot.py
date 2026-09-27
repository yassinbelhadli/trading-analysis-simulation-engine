"""Real TradingView Screenshot Bot — embed URL + clip to remove header."""

import sys, os, asyncio, logging, io
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone
from urllib.parse import quote
import json
from playwright.async_api import async_playwright
from PIL import Image, ImageDraw, ImageFont

from telegram import Bot
from telegram.constants import ParseMode
from config.settings import TELEGRAM_BOT_TOKEN

TELEGRAM_CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID", "7320801946"))

TV_SYMBOLS = {
    "XAUUSD": "OANDA:XAUUSD",
    "US100.cash": "CAPITALCOM:US100",
    "BTCUSD": "COINBASE:BTCUSD",
}
DISPLAY_NAMES = {"XAUUSD": "Gold", "US100.cash": "Nasdaq", "BTCUSD": "Bitcoin"}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("tv_bot")

_SMALL = None
for fn in ["Segoe UI", "Arial", "DejaVuSans"]:
    try:
        _SMALL = ImageFont.truetype(fn, 9)
        break
    except:
        continue
if not _SMALL:
    _SMALL = ImageFont.load_default()


def _build_url(tv_symbol: str, interval: str = "5") -> str:
    overrides = json.dumps({
        "mainSeriesProperties.candleStyle.upColor": "#2962ff",
        "mainSeriesProperties.candleStyle.downColor": "#1a1a1a",
        "mainSeriesProperties.candleStyle.borderUpColor": "#2962ff",
        "mainSeriesProperties.candleStyle.borderDownColor": "#1a1a1a",
        "mainSeriesProperties.candleStyle.wickUpColor": "#2962ff",
        "mainSeriesProperties.candleStyle.wickDownColor": "#1a1a1a",
    })
    disabled = json.dumps([
        "create_volume_indicator_by_default",
        "volume_force_overlay",
    ])
    return (
        "https://s.tradingview.com/widgetembed/"
        f"?symbol={tv_symbol}"
        f"&interval={interval}"
        "&hidesidetoolbar=1"
        "&theme=light"
        "&style=1"
        "&timezone=Etc/UTC"
        "&withfooter=0"
        "&hideideas=1"
        "&noStudies=true"
        f"&overrides={quote(overrides)}"
        f"&disabled_features={quote(disabled)}"
    )


async def capture_chart(symbol_key: str, interval: str = "5") -> bytes:
    url = _build_url(TV_SYMBOLS.get(symbol_key, symbol_key), interval)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1100, "height": 700})
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(5000)

        # Hide top info bar, control bar (zoom/scroll), and TV logo corner
        await page.evaluate("""
            () => {
                document.querySelectorAll('div, span, button, svg, canvas').forEach(el => {
                    const r = el.getBoundingClientRect();
                    const cls = (el.className || '').toString();
                    // 1) Top info bar text (y 38-82, small elements)
                    if (r.y > 38 && r.y < 82 && r.width < 500 && r.height < 80) {
                        el.style.setProperty('display', 'none', 'important');
                    }
                    // 2) Control bar (zoom/scroll buttons above time scale)
                    if (cls.includes('control-bar')) {
                        el.style.setProperty('display', 'none', 'important');
                    }
                    // 3) TradingView logo corner (bottom-right)
                    if (r.x >= 1029 && r.y >= 660) {
                        el.style.setProperty('display', 'none', 'important');
                    }
                });
            }
        """)
        await page.wait_for_timeout(500)

        # Clip: chart + right price scale + time scale (y=38 to y=700)
        result = await page.screenshot(
            clip={"x": 0, "y": 38, "width": 1100, "height": 662}
        )
        await browser.close()

    return result


def _overlay_footer(raw_bytes: bytes, label: str) -> io.BytesIO:
    img = Image.open(io.BytesIO(raw_bytes)).convert("RGBA")
    w, h = img.size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    now = datetime.now(timezone.utc).strftime("%H:%M UTC")
    draw.text((8, h - 14), f"ICT EA PRO | {now}", fill=(120, 120, 120, 80), font=_SMALL, anchor="lt")
    result = Image.alpha_composite(img, overlay)
    buf = io.BytesIO()
    result.save(buf, format="PNG")
    buf.seek(0)
    return buf


async def send_chart(bot: Bot, chat_id: int, symbol_key: str):
    display = DISPLAY_NAMES.get(symbol_key, symbol_key)
    try:
        raw = await capture_chart(symbol_key, "5")
        final_buf = _overlay_footer(raw, display)
        sz_kb = final_buf.seek(0, 2) / 1024
        final_buf.seek(0)

        await bot.send_photo(
            chat_id=chat_id,
            photo=final_buf,
            caption=f"<b>{display}</b> M5 | <code>{sz_kb:.1f}KB</code>",
            parse_mode=ParseMode.HTML,
        )
        logger.info("Sent %s — %.1fKB", display, sz_kb)
    except Exception as e:
        logger.error("Failed %s: %s", symbol_key, e)


async def main():
    token = TELEGRAM_BOT_TOKEN
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not set")
        return

    bot = Bot(token=token)
    me = await bot.get_me()
    logger.info("Bot: @%s", me.username)

    try:
        while True:
            for sym in TV_SYMBOLS:
                await send_chart(bot, TELEGRAM_CHAT_ID, sym)
                await asyncio.sleep(5)
            logger.info("Cycle done. Next in 300s...")
            await asyncio.sleep(300)
    except KeyboardInterrupt:
        logger.info("Shutdown")


if __name__ == "__main__":
    asyncio.run(main())

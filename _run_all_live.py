"""Generate live ICT charts for XAUUSD, BTCUSD, NAS100 and send to Telegram."""
import sys, os, logging, asyncio
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

logging.basicConfig(level=logging.WARNING)
os.environ["PYTHONIOENCODING"] = "utf-8"

# Load env
env_path = Path("config/.env")
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = 7320801946

from media.tv_renderer.tv_data import fetch_ohlc
from media.tv_renderer.ict_analysis import build_snapshot
from media.tv_renderer.renderer import tv_screenshot
from telegram import Bot

SYMBOLS = {"XAUUSD": "BUY", "BTCUSD": "BUY", "NAS100": "SELL"}


async def main():
    bot = Bot(token=BOT_TOKEN)

    for sym, direction in SYMBOLS.items():
        print(f"\n--- {sym} ---")

        ohlc = fetch_ohlc(sym, "15m", 80)
        if not ohlc:
            print(f"  No data")
            continue

        print(f"  Candles: {len(ohlc)}")

        snap = build_snapshot(ohlc, direction)
        if not snap:
            print(f"  Analysis failed")
            continue

        snap["metadata"]["symbol"] = sym
        ev = ohlc[-1]["close"]
        snap["drawing"]["entry"]["price"] = ev
        snap["drawing"]["sl"] = ev * (0.99 if direction == "BUY" else 1.01)
        snap["drawing"]["tp"] = [ev * 1.005, ev * 1.01] if direction == "BUY" else [ev * 0.995, ev * 0.99]
        snap["drawing"]["buy_sell"] = direction

        img = tv_screenshot("live_demo", snap)
        if img:
            print(f"  Chart: {img}")
            with open(img, "rb") as f:
                await bot.send_photo(chat_id=CHAT_ID, photo=f, caption=f"{sym} Live ICT Chart — 15m")
        else:
            print(f"  Render FAILED")

    print("\nAll done.")


if __name__ == "__main__":
    asyncio.run(main())

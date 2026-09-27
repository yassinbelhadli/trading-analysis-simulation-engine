"""Capture clean TradingView chart screenshots via Playwright."""

import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

try:
    from playwright.sync_api import sync_playwright
    _PW_AVAILABLE = True
except ImportError:
    _PW_AVAILABLE = False


SYMBOL_MAP = {
    "XAUUSD": "COMEX%3AGC1%21",
    "BTCUSD": "BITSTAMP%3ABTCUSD",
    "BTCUSDT": "BINANCE%3ABTCUSDT",
    "NAS100": "FX%3ANAS100",
    "SP500": "SP%3ASPX",
}

TIMEFRAME_MAP = {
    "1m": 1, "5m": 5, "15m": 15, "30m": 30,
    "1h": 60, "4h": 240, "1d": "1D",
}

CHART_URL = "https://www.tradingview.com/chart/?symbol={sym}&interval={tf}"




def capture_chart(symbol: str,
                  timeframe: str = "15m",
                  output_path: str = None,
                  width: int = 1280,
                  height: int = 900) -> Optional[Dict[str, Any]]:
    """Capture a clean TradingView chart screenshot + metadata.

    Returns dict with 'path' (str) and 'price_range' ({high, low})
    or None on failure.
    """
    if not _PW_AVAILABLE:
        logger.error("playwright not installed")
        return None

    sym_code = SYMBOL_MAP.get(symbol.upper())
    if not sym_code:
        logger.error("Unknown symbol: %s", symbol)
        return None

    tf_code = TIMEFRAME_MAP.get(timeframe, 15)
    url = CHART_URL.format(sym=sym_code, tf=tf_code)

    if not output_path:
        output_path = f"_tv_{symbol}.png"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(
                viewport={"width": width, "height": height},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
                locale="en-US",
                device_scale_factor=2,
            )
            page = ctx.new_page()

            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(8000)

            # Take viewport screenshot
            page.screenshot(path=output_path, full_page=False)

            browser.close()

            result = Path(output_path)
            if result.exists() and result.stat().st_size > 5000:
                logger.info("Chart captured: %s (%d bytes)", output_path, result.stat().st_size)
                return {"path": str(result), "price_range": None}
            else:
                logger.error("Screenshot too small: %d bytes", result.stat().st_size)
                return None
    except Exception as e:
        logger.error("TV capture failed: %s", e, exc_info=True)
        return None


def capture_clean(symbol: str, timeframe: str = "15m",
                  output_path: str = None) -> Optional[str]:
    """Simple capture returning only the image path."""
    result = capture_chart(symbol, timeframe, output_path)
    if result:
        return result["path"]
    return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import sys, json
    sym = sys.argv[1] if len(sys.argv) > 1 else "XAUUSD"
    res = capture_chart(sym)
    if res:
        print(f"OK: {res['path']}")
        print(f"Price range: {json.dumps(res.get('price_range'))}")
    else:
        print("FAILED")

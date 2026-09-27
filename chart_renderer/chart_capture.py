"""Capture clean TV chart via widget embed + post-process colors."""

import json
import logging
import urllib.parse
import numpy as np
from pathlib import Path
from typing import Optional

import requests
from PIL import Image

logger = logging.getLogger(__name__)

try:
    from playwright.sync_api import sync_playwright
    _PW_AVAILABLE = True
except ImportError:
    _PW_AVAILABLE = False

SYMBOL_MAP = {
    "XAUUSD": "COMEX:GC1!",
    "BTCUSD": "BITSTAMP:BTCUSD",
    "BTCUSDT": "BINANCE:BTCUSDT",
    "NAS100": "FX:NAS100",
}
TIMEFRAME_MAP = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240, "1d": "1D"}

_DISABLED_FEATURES = [
    "header_widget", "header_symbol_search", "go_to_date",
    "show_logo_on_all_charts", "left_toolbar", "control_bar",
    "volume_force_overlay", "create_volume_indicator_by_default",
]


def _build_url(symbol: str, timeframe: str = "15m",
              center_time: Optional[int] = None) -> str:
    sym = SYMBOL_MAP.get(symbol.upper(), symbol)
    tf = TIMEFRAME_MAP.get(timeframe, 15)
    hash_data = {
        "symbol": sym, "frameElementId": "tv", "interval": str(tf),
        "hide_top_toolbar": "1", "hide_legend": "1", "hide_side_toolbar": "1",
        "save_image": "0", "studies": "[]", "theme": "light", "style": "1",
        "studies_overrides": "{}",
        "utm_medium": "widget", "utm_campaign": "chart", "utm_term": sym,
        "page-uri": "__NHTTP__",
    }
    if center_time:
        hash_data["time"] = center_time
    disabled = json.dumps(_DISABLED_FEATURES)
    qs = (
        "hideideas=1&overrides=%7B%7D&enabled_features=%5B%5D"
        f"&disabled_features={urllib.parse.quote(disabled)}&locale=en"
    )
    return f"https://s.tradingview.com/widgetembed/?{qs}#{urllib.parse.quote(json.dumps(hash_data))}"


def _fetch_visible_range(symbol: str) -> Optional[dict]:
    """Fetch last ~200 candles from exchange to determine visible price range."""
    try:
        # Map symbol to Binance symbol
        binance_map = {"BTCUSD": "BTCUSDT", "ETHUSD": "ETHUSDT", "XAUUSD": "XAUUSDT"}
        bin_sym = binance_map.get(symbol.upper(), symbol.upper().replace("USD", "USDT"))
        url = f"https://api.binance.com/api/v3/klines?symbol={bin_sym}&interval=15m&limit=200"
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if not data or not isinstance(data, list):
            logger.warning("No kline data from Binance for %s", symbol)
            return None
        highs = [float(d[2]) for d in data]
        lows = [float(d[3]) for d in data]
        vis_high = max(highs)
        vis_low = min(lows)
        pad = (vis_high - vis_low) * 0.05
        return {"price_high": vis_high + pad, "price_low": vis_low - pad,
                "visible_high": vis_high, "visible_low": vis_low}
    except Exception as e:
        logger.warning("Failed to fetch visible range: %s", e)
        return None


def _recolor(img: Image.Image) -> Image.Image:
    """Recolor: green → blue, red → dark, white → light gray + ensure grid visible."""
    arr = np.array(img.convert("RGB"))
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

    # TV green candle: high green, low red+blue → blue
    green_mask = (g > 100) & (r < 100) & (b < 140) & (g >= r + 20)
    arr[green_mask] = [37, 99, 235]

    # TV red candle: high red, low green+blue → dark
    red_mask = (r > 150) & (g < 130) & (b < 130) & (r >= g + 20)
    arr[red_mask] = [31, 41, 55]

    # Near-white background → light gray (keeps grid visible since grid is darker gray)
    near_white = (r > 240) & (g > 240) & (b > 240)
    # Only replace pure white-ish pixels; grid lines (gray ~220-238) stay
    arr[near_white] = [235, 235, 235]

    return Image.fromarray(arr, "RGB")


def capture_clean(symbol: str, timeframe: str = "15m",
                  output_path: Optional[str] = None,
                  width: int = 1400, height: int = 900,
                  center_time: Optional[int] = None) -> Optional[dict]:
    """Capture clean TV chart via widget embed + recolor.

    Returns {'path': str, 'chart_w': int, 'chart_h': int,
             'full_w': int, 'full_h': int} or None.
    chart_w/h are the main chart canvas (for coordinate mapping).
    full_w/h are the full page (includes price axis).
    """
    if not _PW_AVAILABLE:
        logger.error("playwright not installed")
        return None

    url = _build_url(symbol, timeframe, center_time)
    if not output_path:
        output_path = f"_tv_{symbol}_{timeframe}.png"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(
                viewport={"width": width, "height": height},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
                locale="en-US", device_scale_factor=2,
            )
            page = ctx.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(12000)

            # Find main chart canvas for coordinate mapping
            canvases = page.query_selector_all("canvas")
            if not canvases:
                logger.error("No canvases found")
                browser.close()
                return None

            sizes = [(i, c.bounding_box()) for i, c in enumerate(canvases)]
            sizes = [(i, b) for i, b in sizes if b]
            sizes.sort(key=lambda x: x[1]["width"] * x[1]["height"], reverse=True)
            chart_box = sizes[0][1] if sizes else None
            if not chart_box or chart_box["width"] < 100:
                logger.error("Chart canvas too small")
                browser.close()
                return None

            # Screenshot the chart-widget container (includes chart + price axis + time axis)
            widget = page.query_selector(".chart-widget")
            if widget:
                widget.screenshot(path=output_path)
                wbox = widget.bounding_box()
                fw, fh = int(wbox["width"]), int(wbox["height"])
            else:
                page.screenshot(path=output_path)
                fw, fh = width, height

            browser.close()

        path = Path(output_path)
        if not (path.exists() and path.stat().st_size > 20000):
            logger.error("Capture too small: %d bytes", path.stat().st_size)
            return None

        # Post-process colors
        img = Image.open(output_path)
        img = _recolor(img)
        img.save(output_path)

        # Fetch visible price range from live market data
        price_range = _fetch_visible_range(symbol)

        cw, ch = int(chart_box["width"]), int(chart_box["height"])
        logger.info("Captured: %s (chart %dx%d, full %dx%d, %d bytes)",
                    output_path, cw, ch, fw, fh, path.stat().st_size)
        if price_range:
            logger.info("Visible range: low=%.2f high=%.2f",
                        price_range["visible_low"], price_range["visible_high"])
        return {"path": str(path), "chart_w": cw, "chart_h": ch,
                "full_w": fw, "full_h": fh,
                "price_range": price_range}

    except Exception as e:
        logger.error("Capture failed: %s", e, exc_info=True)
        return None


def capture_minimal(symbol: str, timeframe: str = "15m",
                    output_path: Optional[str] = None) -> Optional[str]:
    res = capture_clean(symbol, timeframe, output_path)
    return res["path"] if res else None

"""Orchestrator: capture TV chart → generate signal card → send Telegram."""

import json
import logging
import time as ttime
from pathlib import Path
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

from dashboard.tradingview_capture import capture_chart
from dashboard.image_generator import generate_card
from dashboard.telegram_sender import send_chart

_HERE = Path(__file__).resolve().parent
STORAGE_DIR = _HERE.parent / "storage" / "charts"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def generate_signal(symbol: str,
                    direction: str,
                    entry_price: float,
                    sl_price: float,
                    tp_prices: List[float],
                    timeframe: str = "15m",
                    icp_data: Dict = None,
                    confidence: float = 94.0,
                    risk_pct: float = 1.0,
                    rr: float = 3.0,
                    session: str = "London",
                    trade_id: str = None,
                    send_telegram: bool = True) -> Optional[str]:
    """Full pipeline: capture TV chart → ICT overlay → send Telegram.

    Returns path to final signal card image.
    """
    symbol = symbol.upper()
    tid = trade_id or f"{symbol}_{int(ttime.time())}"

    # Step 1: Capture TradingView chart
    logger.info("Capturing %s %s chart...", symbol, timeframe)
    raw_path = str(STORAGE_DIR / f"{tid}_raw.png")
    tv_result = capture_chart(symbol, timeframe, output_path=raw_path)
    if not tv_result:
        logger.error("Chart capture failed")
        return None

    chart_path = tv_result["path"]
    price_range = tv_result.get("price_range") or {}

    # Merge price range into ICP data
    full_icp = dict(icp_data or {})
    full_icp["price_range"] = price_range

    # Step 2: Generate professional signal card
    logger.info("Generating signal card...")
    card_path = str(STORAGE_DIR / f"{tid}.png")
    final = generate_card(
        chart_path, symbol,
        timeframe.upper().replace("M", "M") if "m" in timeframe else timeframe,
        direction, entry_price, sl_price, tp_prices,
        icp_data=full_icp,
        confidence=confidence,
        risk_pct=risk_pct,
        rr=rr,
        session=session,
        output_path=card_path,
    )
    if not final:
        logger.error("Signal card generation failed")
        return None

    # Clean up raw chart
    try:
        Path(chart_path).unlink()
    except Exception:
        pass

    # Step 3: Send to Telegram
    if send_telegram:
        caption = (f"{symbol} {timeframe} {direction}\n"
                   f"Entry: {entry_price:.2f} | SL: {sl_price:.2f} | "
                   f"TP: {', '.join(f'{t:.2f}' for t in tp_prices)}")
        sent = send_chart(final, caption)
        if sent:
            logger.info("Signal sent to Telegram")
        else:
            logger.warning("Telegram send failed")

    return final


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import sys, os
    env_path = Path("config/.env")
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

    sym = sys.argv[1] if len(sys.argv) > 1 else "BTCUSD"
    out = generate_signal(sym, "BUY", 64000, 63400, [64400, 64800],
                          session="New York", confidence=91)
    if out:
        print(f"OK: {out}")
    else:
        print("FAILED")

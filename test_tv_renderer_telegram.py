import sys, json, logging
from pathlib import Path
import time as ttime
sys.path.insert(0, str(Path('.').resolve()))
logging.basicConfig(level=logging.DEBUG)
from media.tv_renderer.renderer import tv_screenshot

base_ts = int(ttime.mktime((2024, 1, 1, 9, 0, 0, 0, 0, 0)))
SNAPSHOT = {
    "metadata": {"symbol": "XAUUSD", "timeframe": "M15"},
    "chart": {
        "ohlc": [
            {"time": base_ts + i*900, "open": 3357.0+i*0.4, "high": 3360.0+i*0.5, "low": 3355.0+i*0.3, "close": 3358.0+i*0.4}
            for i in range(60)
        ]
    },
    "structure": {
        "bos": {"start_index": 5, "end_index": 35, "price": 3375.0},
        "choch": {"start_index": 5, "end_index": 25, "price": 3370.0},
        "mss": {"start_index": 28, "end_index": 40, "price": 3385.0},
        "swings": [
            {"type": "LL", "price": 3358.0, "index": 3},
            {"type": "HL", "price": 3362.0, "index": 12},
            {"type": "HH", "price": 3380.0, "index": 22},
            {"type": "LH", "price": 3378.0, "index": 35},
            {"type": "LL", "price": 3365.0, "index": 42},
            {"type": "HL", "price": 3370.0, "index": 48},
        ],
        "swing_high": 3380.0, "swing_low": 3358.0,
    },
    "order_blocks": [{"type": "Bullish OB", "top": 3356.0, "bottom": 3354.0, "fresh": True, "mitigated": False}],
    "fvg": [{"type": "Bullish FVG", "top": 3358.0, "bottom": 3355.0, "mitigated": False}],
    "liquidity": {"sweep_price": 3354.0, "sweep_type": "BSL sell", "pdh": 3395.0, "pdl": 3352.0},
    "session": {"label": "London Killzone", "pdh": 3395.0, "pdl": 3352.0},
    "drawing": {
        "entry": {"price": 3368.25}, "sl": 3352.0, "tp": [3382.0, 3395.0, 3410.0],
        "buy_sell": "BUY", "rr": 3.5
    },
    "trade": {"entry_price": 3368.25, "sl_price": 3352.0, "tp_prices": [3382.0, 3395.0, 3410.0], "direction": "BUY", "rr": 3.5}
}

EXIT = json.loads(json.dumps(SNAPSHOT))
EXIT["drawing"]["exit_price"] = 3392.0
EXIT["drawing"]["realized_pnl"] = 285.0
EXIT["drawing"]["realized_r"] = 1.75
EXIT["drawing"]["exit_reason"] = "TP2"
EXIT["trade"]["exit_price"] = 3392.0
EXIT["trade"]["realized_pnl"] = 285.0
EXIT["trade"]["realized_r"] = 1.75
EXIT["trade"]["exit_reason"] = "TP2"

print("Entry:", tv_screenshot("demo_tv_001", SNAPSHOT))
print("Exit:", tv_screenshot("demo_tv_001", EXIT))
print("OK")

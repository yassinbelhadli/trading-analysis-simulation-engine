"""Quick smoke test for Renderer V2."""
import sys; sys.path.insert(0, '.')
import json, logging
logging.basicConfig(level=logging.DEBUG)

from data.kline_loader import fetch_klines
from detection.engine import analyze
from detection.setup import find_best_setup
from detection.entry import evaluate_setup
from renderer_v2 import render_snapshot, snapshot_to_json

# Fetch data
candles = fetch_klines("BTCUSD", "1h", 500)
print(f"Fetched {len(candles)} candles")

# Run detection
result = analyze(candles)
setup = find_best_setup(result)
if setup:
    signal = evaluate_setup(setup, candles)
    print(f"Setup found: {setup['direction']} Score={setup['score']}")
    print(f"Signal: {signal.get('entry_type')} @ {signal.get('entry_price')}")
else:
    print("No setup found, using analysis result as snapshot")
    signal = None

# Build a minimal snapshot
snap = {
    "metadata": {"symbol": "BTCUSD", "timeframe": "1h", "setup_id": "test_001", "theme": "dark"},
    "chart": {"ohlc": candles},
    "structure": {
        "bos": {"price": candles[-1]["close"], "start_index": 0, "end_index": len(candles)-1, "direction": "BULLISH"},
        "choch": {"price": candles[-1]["close"] * 0.99, "start_index": 50, "end_index": len(candles)-1, "direction": "BULLISH"},
        "swings": [
            {"type": "HH", "price": candles[-10]["high"], "index": len(candles)-10},
            {"type": "HL", "price": candles[-20]["low"], "index": len(candles)-20},
            {"type": "LH", "price": candles[-15]["high"], "index": len(candles)-15},
        ],
        "pdh": candles[-1]["high"] * 1.02,
        "pdl": candles[-1]["low"] * 0.98,
    },
    "order_blocks": [
        {"type": "BULLISH", "top": candles[-5]["close"], "bottom": candles[-5]["low"],
         "anchor_candle": len(candles)-5, "fresh": True},
    ],
    "fvg": [
        {"type": "BULLISH", "top": candles[-8]["high"] * 1.001, "bottom": candles[-8]["low"] * 0.999,
         "candle": len(candles)-8},
    ],
    "liquidity": {"sweep_price": candles[-3]["low"], "sweep_type": "SELL_SIDE"},
    "session": {"pdh": candles[-1]["high"] * 1.02, "pdl": candles[-1]["low"] * 0.98},
    "scoring": {"score": 85, "classification": "high_confidence", "direction": "BUY",
                 "reasons": {"bos": 20, "choch": 15, "active_ob_fvg": 20, "pd_alignment": 10}},
    "drawing": {
        "entry_price": candles[-1]["close"],
        "sl_price": candles[-1]["close"] * 0.98,
        "tp": [candles[-1]["close"] * 1.04],
        "buy_sell": "BUY",
    },
    "trade": {
        "entry_price": candles[-1]["close"],
        "sl_price": candles[-1]["close"] * 0.98,
        "tp_prices": [candles[-1]["close"] * 1.04],
        "direction": "BUY",
    },
}

if signal:
    snap["drawing"]["entry_price"] = signal.get("entry_price")
    snap["drawing"]["sl_price"] = signal.get("stop_loss")
    snap["drawing"]["tp"] = [signal.get("take_profit")]

# Test render
print("\n=== Rendering scene...")
img = render_snapshot(snap, output_path="backtester/reports/renderer_v2_test.png")
print(f"Image: {img.size}")

# Test JSON export
print("\n=== Exporting JSON...")
json_data = snapshot_to_json(snap)
print(f"JSON keys: {list(json_data.keys())}")
print(f"Layers: {[l['type'] for l in json_data['layers']]}")
print(f"Total elements: {sum(len(l['elements']) for l in json_data['layers'])}")

print("\n✅ Renderer V2 smoke test passed!")

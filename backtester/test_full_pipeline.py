"""Full pipeline integration test: Detection → Snapshot → Explainability → Renderer."""
import sys; sys.path.insert(0, '.')
import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")

from data.kline_loader import fetch_klines
from detection.engine import analyze
from detection.setup import find_best_setup
from detection.entry import evaluate_setup
from core_engine.explainability import build_explanation, explain_to_text, explain_to_dict
from renderer_v2 import render_snapshot

# 1. Fetch data
candles = fetch_klines("ETHUSD", "1h", 500)
print(f"1. Candles: {len(candles)}")

# 2. Detection
result = analyze(candles)
setup = find_best_setup(result)

if setup:
    signal = evaluate_setup(setup, candles)
    direction = setup.get("direction", "NEUTRAL")
    score_val = setup.get("score", 0)
    print(f"2. Setup: {direction} Score={score_val} Entry={signal.get('entry_price', 'N/A')}")
else:
    scoring = result.get("scoring", {})
    direction = scoring.get("direction", "NEUTRAL")
    score_val = scoring.get("score", 0)
    print(f"2. No setup (score={score_val}) — using raw analysis as snapshot")
    signal = None

# 3. Build snapshot
snap = {
    "metadata": {"symbol": "ETHUSD", "timeframe": "1h", "setup_id": "full_test"},
    "chart": {"ohlc": candles},
    "structure": result.get("structure", {}),
    "order_blocks": result.get("order_blocks", [])[:3],
    "fvg": (result.get("fvgs", []) or result.get("fvg", []))[:3],
    "liquidity": {"sweep_price": result.get("structure", {}).get("sweep_price"),
                  "sweep_type": "SELL_SIDE"},
    "session": {"pdh": result.get("structure", {}).get("pdh"),
                "pdl": result.get("structure", {}).get("pdl")},
    "scoring": result.get("scoring", {}),
    "drawing": {
        "entry_price": signal["entry_price"] if signal else candles[-1]["close"],
        "sl_price": signal["stop_loss"] if signal else candles[-1]["close"] * 0.98,
        "tp": [signal["take_profit"]] if signal else [candles[-1]["close"] * 1.04],
        "buy_sell": direction,
    },
    "trade": {
        "entry_price": signal["entry_price"] if signal else candles[-1]["close"],
        "sl_price": signal["stop_loss"] if signal else candles[-1]["close"] * 0.98,
        "tp_prices": [signal["take_profit"]] if signal else [candles[-1]["close"] * 1.04],
        "direction": direction,
    },
}

# 4. Explainability
exp = build_explanation(snap)
print(f"3. Explanation: {exp.verdict} Score={exp.score} Confidence={exp.confidence}")
print(f"   Reasons: {len(exp.passed_reasons)} passed / {len(exp.failed_reasons)} failed")

# 5. Render with Explanation
img = render_snapshot(
    snap,
    output_path="backtester/reports/full_pipeline_test.png",
    explanation=exp,
)
print(f"4. Rendered: {img.size}")

# 6. Print explanation text
print(f"\n--- EXPLANATION ---")
print(explain_to_text(exp, detailed=True))

print(f"\nPASSED — Full pipeline: Detection → Snapshot → Explainability → Renderer")

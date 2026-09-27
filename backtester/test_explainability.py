"""Test Explainability Engine with a real snapshot."""
import sys; sys.path.insert(0, '.')
import logging
logging.basicConfig(level=logging.INFO)

from data.kline_loader import fetch_klines
from detection.engine import analyze
from core_engine.explainability import build_explanation, explain_to_text, explain_to_dict

# Fetch real data
candles = fetch_klines("ETHUSD", "1h", 500)
print(f"Candles: {len(candles)}")

# Run detection
result = analyze(candles)
obs = result.get("order_blocks", [])
fvgs = result.get("fvgs", []) or result.get("fvg", [])
struct = result.get("structure", {})
scoring = result.get("scoring", {})
direction = scoring.get("direction", "NEUTRAL")

# Build a realistic snapshot
snap = {
    "metadata": {"symbol": "ETHUSD", "timeframe": "1h", "setup_id": "test_explain"},
    "chart": {"ohlc": candles},
    "structure": struct,
    "order_blocks": obs[:3],
    "fvg": fvgs[:3],
    "liquidity": {"sweep_price": struct.get("sweep_price"), "sweep_type": "SELL_SIDE"},
    "session": {"pdh": struct.get("pdh"), "pdl": struct.get("pdl")},
    "scoring": scoring,
    "drawing": {
        "entry_price": candles[-1]["close"],
        "sl_price": candles[-1]["close"] * 0.98,
        "tp": [candles[-1]["close"] * 1.04],
        "buy_sell": direction,
    },
    "trade": {
        "entry_price": candles[-1]["close"],
        "sl_price": candles[-1]["close"] * 0.98,
        "tp_prices": [candles[-1]["close"] * 1.04],
        "direction": direction,
    },
}

# Build explanation
exp = build_explanation(snap)
print(f"\n=== EXPLANATION ===")
print(f"Verdict: {exp.verdict}")
print(f"Score: {exp.score}/100")
print(f"Confidence: {exp.confidence}")
print(f"Reasons: {len(exp.reasons)} ({len(exp.passed_reasons)} passed, {len(exp.failed_reasons)} failed)")
print(f"Warnings: {len(exp.warnings)}")
print(f"Invalidations: {len(exp.invalidations)}")
print(f"Tradeable: {exp.is_tradeable}")

# Print formatted text
print(f"\n{'='*50}")
print(explain_to_text(exp, detailed=True))

# Dict export
d = explain_to_dict(exp)
print(f"\nDict keys: {list(d.keys())}")
print(f"Reason codes: {[r['code'] for r in d['reasons']]}")

print("\nPASSED")

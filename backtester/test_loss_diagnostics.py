import pandas as pd
from pathlib import Path

TRADES_FILE = Path("data/processed/XAUUSD_M15_execution_layer_result.csv")

df = pd.read_csv(TRADES_FILE)

losses = df[
    (df["close_reason"] == "SL_HIT")
    & (df["pnl_money"] < 0)
].copy()

print("=" * 70)
print("LOSS DIAGNOSTICS")
print("=" * 70)

print("Real Losses:", len(losses))

print("\n===== BY ENTRY SOURCE =====")
print(losses["entry_source"].value_counts(dropna=False))

print("\n===== BY DIRECTION =====")
print(losses["direction"].value_counts(dropna=False))

print("\n===== SCORE STATS =====")
print(losses[["setup_score", "confidence_score", "required_score"]].describe())

print("\n===== RR STATS =====")
print(losses["rr"].describe())

print("\n===== SL DISTANCE STATS =====")
losses["sl_distance"] = (losses["entry_price"] - losses["stop_loss"]).abs()
print(losses["sl_distance"].describe())

print("\n===== REAL LOSSES DETAILS =====")
print(
    losses[
        [
            "trade_id",
            "direction",
            "entry_source",
            "setup_score",
            "confidence_score",
            "required_score",
            "entry_price",
            "stop_loss",
            "take_profit",
            "rr",
            "sl_distance",
            "actual_risk_percent",
            "pnl_money",
            "close_reason",
        ]
    ].sort_values("pnl_money").to_string()
)

print("=" * 70)
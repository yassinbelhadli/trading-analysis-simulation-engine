import pandas as pd
from pathlib import Path

TRADES_FILE = Path("data/processed/XAUUSD_M15_execution_layer_result.csv")

df = pd.read_csv(TRADES_FILE)

df["pnl_money"] = pd.to_numeric(df["pnl_money"], errors="coerce").fillna(0)
df["setup_score"] = pd.to_numeric(df["setup_score"], errors="coerce").fillna(0)
df["confidence_score"] = pd.to_numeric(df["confidence_score"], errors="coerce").fillna(0)

losses = df[
    (df["close_reason"] == "SL_HIT")
    & (df["pnl_money"] < 0)
].copy()

print("=" * 70)
print("LOSS REASON BREAKDOWN")
print("=" * 70)

print("Real Losses:", len(losses))

print("\n===== LOSSES BY ENTRY SOURCE =====")
print(losses["entry_source"].value_counts(dropna=False))

print("\n===== LOSSES BY DIRECTION =====")
print(losses["direction"].value_counts(dropna=False))

print("\n===== LOSSES BY ENTRY SOURCE + DIRECTION =====")
print(losses.groupby(["entry_source", "direction"]).size())

print("\n===== LOSS SCORE STATS BY ENTRY SOURCE =====")
print(
    losses.groupby("entry_source")[["setup_score", "confidence_score", "pnl_money"]]
    .agg(["count", "mean", "min", "max"])
)

print("\n===== LOSS DETAILS =====")
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
            "pnl_money",
            "close_reason",
        ]
    ].sort_values("pnl_money").to_string(index=False)
)

print("=" * 70)
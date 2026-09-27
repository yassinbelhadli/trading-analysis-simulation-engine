import pandas as pd
from pathlib import Path

TRADES_FILE = Path("data/processed/XAUUSD_M15_execution_layer_result.csv")
EVENTS_FILE = Path("data/processed/XAUUSD_M15_execution_events.csv")

trades = pd.read_csv(TRADES_FILE)

trades["pnl_money"] = pd.to_numeric(trades["pnl_money"], errors="coerce").fillna(0)
trades["setup_score"] = pd.to_numeric(trades["setup_score"], errors="coerce").fillna(0)
trades["confidence_score"] = pd.to_numeric(trades["confidence_score"], errors="coerce").fillna(0)

real_losses = trades[
    (trades["close_reason"] == "SL_HIT")
    & (trades["pnl_money"] < 0)
].copy()

print("=" * 70)
print("HTF ALIGNMENT CHECK - REAL LOSSES")
print("=" * 70)

print("Real losses:", len(real_losses))

cols = [
    "trade_id",
    "setup_id",
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
    "open_time",
    "close_time",
    "close_reason",
]

cols = [c for c in cols if c in real_losses.columns]

print("\n===== REAL LOSS DETAILS =====")
print(real_losses[cols].sort_values("open_time").to_string(index=False))

print("\n===== LOSS BY ENTRY SOURCE =====")
print(real_losses["entry_source"].value_counts(dropna=False))

print("\n===== LOSS BY DIRECTION =====")
print(real_losses["direction"].value_counts(dropna=False))

print("\n===== IMPORTANT NOTE =====")
print("This file currently checks loss trades only.")
print("Next step: add HTF_Bias / HTF_Trend into execution CSV from EntryManager metadata.")
print("=" * 70)
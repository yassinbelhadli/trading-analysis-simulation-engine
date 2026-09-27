import pandas as pd
from pathlib import Path

EVENTS_FILE = Path("data/processed/BTCUSDm_M15_execution_events.csv")

if not EVENTS_FILE.exists():
    raise FileNotFoundError(
        f"Missing file: {EVENTS_FILE}\n"
        "Run first: python backtester/test_multi_symbol_execution.py"
    )

events = pd.read_csv(EVENTS_FILE)

print("=" * 70)
print("BTC REJECT BREAKDOWN")
print("=" * 70)

print("\n===== ALL REASONS =====")
print(events["reason"].value_counts(dropna=False))

rejects = events[events["event"] == "ENTRY_REJECTED"].copy()

print("\n===== ENTRY REJECTS ONLY =====")
print(rejects["reason"].value_counts(dropna=False))

for reason in [
    "TRADE_QUALITY_LOW_DYNAMIC_SETUP_SCORE",
    "TRADE_QUALITY_SL_TOO_WIDE",
    "TRADE_QUALITY_RAW_LOT_BELOW_MIN_LOT",
    "SETUP_NOT_APPROVED",
    "ZONE_DIRECTION_MISMATCH",
]:
    part = rejects[rejects["reason"] == reason].copy()

    print("\n" + "=" * 70)
    print(reason)
    print("=" * 70)
    print("Count:", len(part))

    if len(part) > 0:
        cols = [
            "time",
            "price",
            "symbol",
            "direction",
            "entry_source",
            "sl_source",
            "lot_size",
            "sl",
            "tp",
            "trade_id",
        ]

        available_cols = [c for c in cols if c in part.columns]
        print(part[available_cols].head(50).to_string(index=False))

OUT = Path("data/processed/BTCUSDm_reject_breakdown.csv")
rejects.to_csv(OUT, index=False)

print("\n" + "=" * 70)
print(f"Saved: {OUT}")
print("=" * 70)
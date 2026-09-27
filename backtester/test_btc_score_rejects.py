import pandas as pd
from pathlib import Path

EVENTS_FILE = Path("data/processed/BTCUSDm_M15_execution_events.csv")

events = pd.read_csv(EVENTS_FILE)

rejects = events[
    events["reason"].astype(str).str.contains("LOW_DYNAMIC_SETUP_SCORE", na=False)
].copy()

print("=" * 70)
print("BTC LOW SCORE REJECTS")
print("=" * 70)

print("Rejected low score setups:", len(rejects))

print("\nColumns:")
print(rejects.columns.tolist())

print("\nPreview:")
print(rejects.head(30).to_string(index=False))

OUT = Path("data/processed/BTCUSDm_low_score_rejects.csv")
rejects.to_csv(OUT, index=False)

print("=" * 70)
print(f"Saved: {OUT}")
print("=" * 70)
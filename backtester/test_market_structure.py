import pandas as pd
from pathlib import Path
from core_engine.detection.market_structure import MarketStructureDetector

ROOT = Path(__file__).resolve().parents[1]

DATA = ROOT / "data" / "raw" / "XAUUSD_M15.csv"
OUT = ROOT / "data" / "processed" / "XAUUSD_M15_structure_result1.csv"

OUT.parent.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(DATA)

df["Time"] = pd.to_datetime(df["Time"])
df.set_index("Time", inplace=True)

engine = MarketStructureDetector()

result = engine.process_structure(df)

# ===== Statistics =====

print("=" * 50)
print("Rows:", len(result))
print("BOS:", result["BOS"].sum())
print("CHoCH:", result["CHoCH"].sum())
print("MSS:", result["MSS"].sum())
print("Sweeps:", result["Basic_Liquidity_Sweep"].sum())

print("\nMarket Trend Distribution:")
print(result["Market_Trend"].value_counts())

print("=" * 50)

# ===== Save CSV =====

result.to_csv(OUT)

print(f"Saved: {OUT}")
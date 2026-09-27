import pandas as pd
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from core_engine.detection.market_structure import MarketStructureDetector
from core_engine.detection.liquidity import LiquidityEngine

DATA = ROOT / "data" / "raw" / "XAUUSD_M15.csv"
OUT = ROOT / "data" / "processed" / "XAUUSD_M15_liquidity_result.csv"

OUT.parent.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(DATA)
df["Time"] = pd.to_datetime(df["Time"])
df.set_index("Time", inplace=True)

structure_engine = MarketStructureDetector()
df = structure_engine.process_structure(df)

liquidity_engine = LiquidityEngine()
result = liquidity_engine.process_liquidity(df)

print("=" * 50)
print("Rows:", len(result))

print("\nColumns:")
print(result.columns.tolist())

print("\nLiquidity Sweeps:", result["Liquidity_Sweep"].sum() if "Liquidity_Sweep" in result.columns else "COLUMN MISSING")
print("Valid Sweeps:", result["Valid_Sweep"].sum() if "Valid_Sweep" in result.columns else "COLUMN MISSING")
print("Sweep Confirmed:", result["Sweep_Confirmed"].sum() if "Sweep_Confirmed" in result.columns else "COLUMN MISSING")

print("\nLiquidity Sources:")
print(result["Liquidity_Source"].value_counts(dropna=True) if "Liquidity_Source" in result.columns else "COLUMN MISSING")

print("\nSweep Types:")
print(result["Sweep_Type"].value_counts(dropna=True) if "Sweep_Type" in result.columns else "COLUMN MISSING")

print("=" * 50)

result.to_csv(OUT)
print(f"Saved: {OUT}")
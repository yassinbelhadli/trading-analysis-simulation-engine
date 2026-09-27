import pandas as pd
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from core_engine.detection.market_structure import MarketStructureDetector
from core_engine.detection.liquidity import LiquidityEngine
from core_engine.detection.fair_value_gap import FVGDetector

DATA = ROOT / "data" / "raw" / "XAUUSD_M15.csv"
OUT = ROOT / "data" / "processed" / "XAUUSD_M15_fvg_result.csv"

OUT.parent.mkdir(parents=True, exist_ok=True)

# Load Data
df = pd.read_csv(DATA)

df["Time"] = pd.to_datetime(df["Time"])
df.set_index("Time", inplace=True)

# 1. Market Structure
structure_engine = MarketStructureDetector()
df = structure_engine.process_structure(df)

# 2. Liquidity
liquidity_engine = LiquidityEngine()
df = liquidity_engine.process_liquidity(df)

# 3. FVG
fvg_engine = FVGDetector()
result = fvg_engine.process_fvg(df)

# Save
result.to_csv(OUT)

# Stats
print("=" * 60)

print("Rows:", len(result))

print("Bullish FVG:", result["Bullish_FVG"].sum())
print("Bearish FVG:", result["Bearish_FVG"].sum())

print("Mitigated FVG:", result["FVG_Mitigated"].sum())

print("\nFVG Types:")
print(result["FVG_Type"].value_counts(dropna=True))

print("\nActive FVG:")

active_fvg = result[
    (result["FVG_Type"].notna()) &
    (result["FVG_Mitigated"] == False)
]

print(len(active_fvg))

print("\nActive FVG Preview:")

if len(active_fvg) > 0:
    print(
        active_fvg[
            [
                "Close",
                "FVG_Type",
                "FVG_Upper",
                "FVG_Lower",
                "FVG_Midpoint",
                "FVG_Size",
                "FVG_ID"
            ]
        ].tail(10)
    )
else:
    print("No Active FVG Found")

print("=" * 60)

print(f"Saved: {OUT}")
import pandas as pd
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from core_engine.detection.market_structure import MarketStructureDetector
from core_engine.detection.liquidity import LiquidityEngine
from core_engine.detection.fair_value_gap import FVGDetector
from core_engine.detection.order_blocks import OrderBlockEngine

DATA = ROOT / "data" / "raw" / "XAUUSD_M15.csv"
OUT = ROOT / "data" / "processed" / "XAUUSD_M15_order_blocks_result.csv"

OUT.parent.mkdir(parents=True, exist_ok=True)

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
df = fvg_engine.process_fvg(df)

# 4. Order Blocks
ob_engine = OrderBlockEngine()
result = ob_engine.process_order_blocks(df)

result.to_csv(OUT)

print("=" * 60)
print("Rows:", len(result))

print("Bullish OB:", result["Bullish_OB"].sum())
print("Bearish OB:", result["Bearish_OB"].sum())
print("Valid OB:", result["OB_Valid"].sum())
print("Mitigated OB:", result["OB_Mitigated"].sum())

print("\nOB Types:")
print(result["OB_Type"].value_counts(dropna=True))

print("\nOB Context:")
print(result["OB_Context"].value_counts(dropna=True))

print("\nValid OB Preview:")
valid_ob = result[
    (result["OB_Type"].notna()) &
    (result["OB_Valid"] == True)
]

if len(valid_ob) > 0:
    print(
        valid_ob[
            [
                "Close",
                "OB_Type",
                "OB_Upper",
                "OB_Lower",
                "OB_Midpoint",
                "OB_Size",
                "OB_Context",
                "OB_Liquidity_Score",
                "OB_Touches",
                "OB_ID"
            ]
        ].tail(10)
    )
else:
    print("No Valid OB Found")

print("=" * 60)
print(f"Saved: {OUT}")
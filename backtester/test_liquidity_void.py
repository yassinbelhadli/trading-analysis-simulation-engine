import pandas as pd
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from core_engine.detection.market_structure import MarketStructureDetector
from core_engine.detection.liquidity import LiquidityEngine
from core_engine.detection.fair_value_gap import FVGDetector
from core_engine.detection.order_blocks import OrderBlockEngine
from core_engine.detection.volume_imbalance import VolumeImbalanceDetector
from core_engine.detection.liquidity_void import LiquidityVoidDetector

DATA = ROOT / "data" / "raw" / "XAUUSD_M15.csv"
OUT = ROOT / "data" / "processed" / "XAUUSD_M15_liquidity_void_result.csv"

OUT.parent.mkdir(parents=True, exist_ok=True)

# Load Data
df = pd.read_csv(DATA)

df["Time"] = pd.to_datetime(df["Time"])
df.set_index("Time", inplace=True)

# Market Structure
df = MarketStructureDetector().process_structure(df)

# Liquidity
df = LiquidityEngine().process_liquidity(df)

# FVG
df = FVGDetector().process_fvg(df)

# Order Blocks
df = OrderBlockEngine().process_order_blocks(df)

# Volume Imbalance
df = VolumeImbalanceDetector().process_volume_imbalance(df)

# Liquidity Void
result = LiquidityVoidDetector().process_liquidity_void(df)

# Save CSV
result.to_csv(OUT)

print("=" * 60)

print("Rows:", len(result))

print("Bullish LV:", result["Bullish_LV"].sum())
print("Bearish LV:", result["Bearish_LV"].sum())

print("Valid LV:", result["LV_Valid"].sum())
print("Mitigated LV:", result["LV_Mitigated"].sum())

print("\nLV Types:")
print(result["LV_Type"].value_counts(dropna=True))

print("\nLV Context:")
print(result["LV_Context"].value_counts(dropna=True))

active_lv = result[
    (result["LV_Type"].notna()) &
    (result["LV_Mitigated"] == False)
]

print("\nActive LV:", len(active_lv))

print("\nActive LV Preview:")

if len(active_lv) > 0:
    print(
        active_lv[
            [
                "Close",
                "LV_Type",
                "LV_Upper",
                "LV_Lower",
                "LV_Midpoint",
                "LV_Size",
                "LV_Strength",
                "LV_Context",
                "LV_Valid",
                "LV_ID"
            ]
        ].tail(10)
    )
else:
    print("No Active LV Found")

print("=" * 60)
print(f"Saved: {OUT}")
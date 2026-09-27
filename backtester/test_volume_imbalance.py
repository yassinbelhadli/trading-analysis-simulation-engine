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

DATA = ROOT / "data" / "raw" / "XAUUSD_M15.csv"
OUT = ROOT / "data" / "processed" / "XAUUSD_M15_volume_imbalance_result.csv"

OUT.parent.mkdir(parents=True, exist_ok=True)

# =========================
# LOAD DATA
# =========================

df = pd.read_csv(DATA)

df["Time"] = pd.to_datetime(df["Time"])
df.set_index("Time", inplace=True)

# =========================
# MARKET STRUCTURE
# =========================

structure_engine = MarketStructureDetector()
df = structure_engine.process_structure(df)

# =========================
# LIQUIDITY
# =========================

liquidity_engine = LiquidityEngine()
df = liquidity_engine.process_liquidity(df)

# =========================
# FAIR VALUE GAP
# =========================

fvg_engine = FVGDetector()
df = fvg_engine.process_fvg(df)

# =========================
# ORDER BLOCKS
# =========================

ob_engine = OrderBlockEngine()
df = ob_engine.process_order_blocks(df)

# =========================
# VOLUME IMBALANCE
# =========================

vi_engine = VolumeImbalanceDetector()
result = vi_engine.process_volume_imbalance(df)

# =========================
# SAVE RESULTS
# =========================

result.to_csv(OUT)

# =========================
# VOLUME IMBALANCE STATS
# =========================

print("=" * 60)

print("Rows:", len(result))

print("Bullish VI:", result["Bullish_VI"].sum())
print("Bearish VI:", result["Bearish_VI"].sum())

print("Valid VI:", result["VI_Valid"].sum())
print("Mitigated VI:", result["VI_Mitigated"].sum())

print("\nVI Types:")
print(result["VI_Type"].value_counts(dropna=True))

print("\nVI Context:")
print(result["VI_Context"].value_counts(dropna=True))

active_vi = result[
    (result["VI_Type"].notna()) &
    (result["VI_Mitigated"] == False)
]

print("\nActive VI:", len(active_vi))

print("\nActive VI Preview:")

if len(active_vi) > 0:
    print(
        active_vi[
            [
                "Close",
                "VI_Type",
                "VI_Upper",
                "VI_Lower",
                "VI_Midpoint",
                "VI_Size",
                "VI_Strength",
                "VI_Context",
                "VI_Valid",
                "VI_ID"
            ]
        ].tail(10)
    )
else:
    print("No Active VI Found")

# =========================
# FULL ENGINE STATS
# =========================

print("\n===== FINAL ENGINE STATS =====")

print("BOS:", result["BOS"].sum())
print("CHoCH:", result["CHoCH"].sum())
print("MSS:", result["MSS"].sum())

print("Liquidity Sweeps:", result["Liquidity_Sweep"].sum())
print("Valid Sweeps:", result["Valid_Sweep"].sum())

print("Bullish FVG:", result["Bullish_FVG"].sum())
print("Bearish FVG:", result["Bearish_FVG"].sum())

print("Bullish OB:", result["Bullish_OB"].sum())
print("Bearish OB:", result["Bearish_OB"].sum())

print("Bullish VI:", result["Bullish_VI"].sum())
print("Bearish VI:", result["Bearish_VI"].sum())

print("=" * 60)

print(f"Saved: {OUT}")
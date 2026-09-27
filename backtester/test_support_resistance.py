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
from core_engine.detection.premium_discount import PremiumDiscountDetector
from core_engine.detection.support_resistance import SupportResistanceDetector

DATA = ROOT / "data" / "raw" / "XAUUSD_M15.csv"
OUT = ROOT / "data" / "processed" / "XAUUSD_M15_support_resistance_result.csv"

OUT.parent.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(DATA)
df["Time"] = pd.to_datetime(df["Time"])
df.set_index("Time", inplace=True)

df = MarketStructureDetector().process_structure(df)
df = LiquidityEngine().process_liquidity(df)
df = FVGDetector().process_fvg(df)
df = OrderBlockEngine().process_order_blocks(df)
df = VolumeImbalanceDetector().process_volume_imbalance(df)
df = LiquidityVoidDetector().process_liquidity_void(df)
df = PremiumDiscountDetector().process_premium_discount(df)

sr_engine = SupportResistanceDetector()
result = sr_engine.process_support_resistance(df)

result.to_csv(OUT)

print("=" * 60)
print("Rows:", len(result))

print("\nSR States:")
print(result["SR_State"].value_counts(dropna=True))

print("\nNear Support:", result["Near_Support"].sum())
print("Near Resistance:", result["Near_Resistance"].sum())

print("\nSupport Broken:", result["Support_Broken"].sum())
print("Resistance Broken:", result["Resistance_Broken"].sum())

print("\nValid Buy SR:", result["SR_Valid_Buy"].sum())
print("Valid Sell SR:", result["SR_Valid_Sell"].sum())

print("\nLatest SR Summary:")
print(sr_engine.get_latest_sr(result))

print("\nPreview:")
print(
    result[
        [
            "Close",
            "Market_Trend",
            "Support_Level",
            "Resistance_Level",
            "Near_Support",
            "Near_Resistance",
            "Support_Touches",
            "Resistance_Touches",
            "SR_State",
            "SR_Strength",
            "SR_Valid_Buy",
            "SR_Valid_Sell",
            "SR_ID"
        ]
    ].tail(10)
)

print("=" * 60)
print(f"Saved: {OUT}")
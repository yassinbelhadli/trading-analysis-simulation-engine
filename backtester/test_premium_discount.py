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

DATA = ROOT / "data" / "raw" / "XAUUSD_M15.csv"
OUT = ROOT / "data" / "processed" / "XAUUSD_M15_premium_discount_result.csv"

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

pd_engine = PremiumDiscountDetector()
result = pd_engine.process_premium_discount(df)

result.to_csv(OUT)

print("=" * 60)
print("Rows:", len(result))

print("\nPD States:")
print(result["PD_State"].value_counts(dropna=True))

print("\nValid Buy PD:", result["PD_Valid_Buy"].sum())
print("Valid Sell PD:", result["PD_Valid_Sell"].sum())

print("\nPremium:", result["Premium_Zone"].sum())
print("Discount:", result["Discount_Zone"].sum())
print("Equilibrium:", result["Equilibrium_Zone"].sum())

print("\nLatest PD Summary:")
print(pd_engine.get_pd_summary(result))

print("\nPreview:")
print(
    result[
        [
            "Close",
            "Market_Trend",
            "PD_Range_High",
            "PD_Range_Low",
            "EQ_Level",
            "PD_State",
            "PD_Position",
            "PD_Valid_Buy",
            "PD_Valid_Sell",
            "PD_ID"
        ]
    ].tail(10)
)

print("=" * 60)
print(f"Saved: {OUT}")
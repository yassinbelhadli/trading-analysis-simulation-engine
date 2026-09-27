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
from core_engine.detection.candle_patterns import CandlePatternDetector

DATA = ROOT / "data" / "raw" / "XAUUSD_M15.csv"
OUT = ROOT / "data" / "processed" / "XAUUSD_M15_candle_patterns_result.csv"

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
df = SupportResistanceDetector().process_support_resistance(df)

candle_engine = CandlePatternDetector()
result = candle_engine.process_candle_patterns(df)

result.to_csv(OUT)

print("=" * 60)
print("Rows:", len(result))

print("\nCandle Pattern Counts:")
print("Bullish Engulfing:", result["Bullish_Engulfing"].sum())
print("Bearish Engulfing:", result["Bearish_Engulfing"].sum())
print("Bullish Rejection:", result["Bullish_Rejection"].sum())
print("Bearish Rejection:", result["Bearish_Rejection"].sum())
print("Strong Bullish Close:", result["Strong_Bullish_Close"].sum())
print("Strong Bearish Close:", result["Strong_Bearish_Close"].sum())
print("Inside Bar:", result["Inside_Bar"].sum())
print("Doji:", result["Doji"].sum())

print("\nValid Candle Signals:")
print("Candle Valid Buy:", result["Candle_Valid_Buy"].sum())
print("Candle Valid Sell:", result["Candle_Valid_Sell"].sum())

print("\nCandle Directions:")
print(result["Candle_Direction"].value_counts(dropna=True))

print("\nTop Candle Patterns:")
print(result["Candle_Pattern"].value_counts(dropna=True).head(20))

print("\nLatest Candle Summary:")
print(candle_engine.get_latest_pattern(result))

active_patterns = result[result["Candle_Pattern"].notna()]

print("\nRecent Candle Pattern Preview:")

if len(active_patterns) > 0:
    print(
        active_patterns[
            [
                "Close",
                "Market_Trend",
                "PD_State",
                "SR_State",
                "Candle_Pattern",
                "Candle_Direction",
                "Candle_Strength",
                "Candle_Valid_Buy",
                "Candle_Valid_Sell",
                "Candle_ID"
            ]
        ].tail(15)
    )
else:
    print("No Candle Patterns Found")

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
print("Bullish LV:", result["Bullish_LV"].sum())
print("Bearish LV:", result["Bearish_LV"].sum())
print("Premium:", result["Premium_Zone"].sum())
print("Discount:", result["Discount_Zone"].sum())
print("Near Support:", result["Near_Support"].sum())
print("Near Resistance:", result["Near_Resistance"].sum())

print("=" * 60)
print(f"Saved: {OUT}")
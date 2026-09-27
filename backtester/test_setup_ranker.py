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

from core_engine.scoring.score_engine import ScoreEngine
from core_engine.scoring.setup_ranker import SetupRanker


DATA = ROOT / "data" / "raw" / "XAUUSD_M15.csv"
OUT = ROOT / "data" / "processed" / "XAUUSD_M15_setup_ranker_result.csv"

OUT.parent.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(DATA)
df["Time"] = pd.to_datetime(df["Time"])
df.set_index("Time", inplace=True)

# 1. Detection pipeline
df = MarketStructureDetector().process_structure(df)
df = LiquidityEngine().process_liquidity(df)
df = FVGDetector().process_fvg(df)
df = OrderBlockEngine().process_order_blocks(df)
df = VolumeImbalanceDetector().process_volume_imbalance(df)
df = LiquidityVoidDetector().process_liquidity_void(df)
df = PremiumDiscountDetector().process_premium_discount(df)
df = SupportResistanceDetector().process_support_resistance(df)
df = CandlePatternDetector().process_candle_patterns(df)

# 2. Score engine
df = ScoreEngine().process_score(df)

# 3. Setup ranker
ranker = SetupRanker(
    min_score=70,
    premium_score=85,
    max_daily_setups=6,
    min_daily_setups_target=3,
    cooldown_candles=8,
    max_same_direction_per_day=4
)

result = ranker.process_rankings(df)
approved = ranker.get_approved_setups(result)

result.to_csv(OUT)

print("=" * 70)
print("Rows:", len(result))

print("\n===== SCORE STATS =====")
print("Max Score:", result["Setup_Score"].max())
print("Avg Score:", round(result["Setup_Score"].mean(), 2))

print("\nSetup Quality:")
print(result["Setup_Quality"].value_counts(dropna=False))

print("\nSetup Rank:")
print(result["Setup_Rank"].value_counts(dropna=False))

print("\n===== APPROVED SETUPS =====")
print("Approved:", result["Setup_Approved"].sum())

print("\nApproved By Direction:")
print(approved["Trade_Direction"].value_counts(dropna=False))

print("\nApproved By Session:")
print(approved["Setup_Session"].value_counts(dropna=False))

print("\nApproved Per Day:")
print(result.groupby("Setup_Date")["Setup_Approved"].sum())

print("\nDaily Target OK:")
print(
    result.groupby("Setup_Date")["Daily_Setup_Target_OK"]
    .max()
    .value_counts(dropna=False)
)

print("\nReject Reasons:")
print(result["Setup_Reject_Reason"].value_counts(dropna=False).head(20))

print("\nApproved Preview:")
if len(approved) > 0:
    print(
        approved[
            [
                "Close",
                "Trade_Direction",
                "Setup_Score",
                "Setup_Rank",
                "Setup_Session",
                "Market_Trend",
                "MSS",
                "MSS_Type",
                "CHoCH",
                "BOS",
                "Valid_Sweep",
                "Liquidity_Rank",
                "PD_State",
                "Candle_Pattern",
                "Setup_ID"
            ]
        ].tail(20)
    )
else:
    print("No approved setups found")

print("=" * 70)
print(f"Saved: {OUT}")
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
from core_engine.scoring.confidence_score import ConfidenceScoreEngine


DATA = ROOT / "data" / "raw" / "XAUUSD_M15.csv"
OUT = ROOT / "data" / "processed" / "XAUUSD_M15_confidence_score_result.csv"

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

# 2. Scoring
df = ScoreEngine().process_score(df)

# 3. Ranking
ranker = SetupRanker(
    min_score=70,
    premium_score=85,
    max_daily_setups=6,
    min_daily_setups_target=3,
    cooldown_candles=8,
    max_same_direction_per_day=4
)

df = ranker.process_rankings(df)

# 4. Confidence
confidence_engine = ConfidenceScoreEngine(
    min_confidence=55,
    premium_confidence=70,
    elite_confidence=85,
    max_confidence=98
)

result = confidence_engine.process_confidence(df)
tradeable = confidence_engine.get_tradeable_setups(result)

result.to_csv(OUT)

print("=" * 70)
print("Rows:", len(result))

print("\n===== SETUP RANKER =====")
print("Approved setups:", result["Setup_Approved"].sum())
print("Setup ranks:")
print(result["Setup_Rank"].value_counts(dropna=False))

print("\n===== CONFIDENCE SUMMARY =====")
print(confidence_engine.get_confidence_summary(result))

print("\nConfidence Labels:")
print(result["Confidence_Label"].value_counts(dropna=False))

print("\nConfidence Approved:", result["Confidence_Approved"].sum())

print("\nTradeable By Direction:")
print(tradeable["Trade_Direction"].value_counts(dropna=False))

print("\nTradeable By Session:")
print(tradeable["Setup_Session"].value_counts(dropna=False))

print("\nTradeable Per Day:")
print(result.groupby("Setup_Date")["Confidence_Approved"].sum())

print("\nConfidence Reasons:")
print(result["Confidence_Reason"].value_counts(dropna=False).head(20))

print("\nTradeable Preview:")
if len(tradeable) > 0:
    print(
        tradeable[
            [
                "Close",
                "Trade_Direction",
                "Setup_Score",
                "Setup_Rank",
                "Confidence_Score",
                "Confidence_Label",
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
                "Setup_ID",
            ]
        ].tail(20)
    )
else:
    print("No tradeable setups found")

print("=" * 70)
print(f"Saved: {OUT}")
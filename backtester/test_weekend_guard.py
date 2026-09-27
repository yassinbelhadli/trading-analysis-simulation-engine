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

from core_engine.sessions.killzones import KillzoneEngine
from core_engine.sessions.london_session import LondonSessionEngine
from core_engine.sessions.newyork_session import NewYorkSessionEngine

from core_engine.risk.weekend_guard import WeekendGuard


DATA = ROOT / "data" / "raw" / "XAUUSD_M15.csv"
OUT = ROOT / "data" / "processed" / "XAUUSD_M15_weekend_guard_result.csv"

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

# 2. Scoring pipeline
df = ScoreEngine().process_score(df)

df = SetupRanker(
    min_score=70,
    premium_score=85,
    max_daily_setups=6,
    min_daily_setups_target=3,
    cooldown_candles=8,
    max_same_direction_per_day=4
).process_rankings(df)

df = ConfidenceScoreEngine(
    min_confidence=55,
    premium_confidence=70,
    elite_confidence=85,
    max_confidence=98
).process_confidence(df)

# 3. Sessions pipeline
df = KillzoneEngine().process_killzones(df)
df = LondonSessionEngine().process_london_session(df)
df = NewYorkSessionEngine().process_newyork_session(df)

# 4. Weekend guard
weekend_guard = WeekendGuard(
    friday_cutoff_hour=19,
    monday_resume_hour=10,
    block_weekend=True
)

result = weekend_guard.process_weekend_guard(df)

# 5. Final trade permission
result["Final_Trade_Allowed"] = (
    (result["Confidence_Approved"] == True)
    & (
        (result["Session_Trade_Allowed"] == True)
        | (result["London_Trade_Allowed"] == True)
        | (result["NewYork_Trade_Allowed"] == True)
    )
    & (result["Weekend_Trade_Allowed"] == True)
)

result["Final_Block_Reason"] = None

result.loc[result["Confidence_Approved"] == False, "Final_Block_Reason"] = "CONFIDENCE_NOT_APPROVED"

session_not_allowed = (
    (result["Confidence_Approved"] == True)
    & (result["Session_Trade_Allowed"] == False)
    & (result["London_Trade_Allowed"] == False)
    & (result["NewYork_Trade_Allowed"] == False)
)

result.loc[session_not_allowed, "Final_Block_Reason"] = "SESSION_NOT_ALLOWED"

weekend_blocked = (
    (result["Confidence_Approved"] == True)
    & (result["Weekend_Trade_Allowed"] == False)
)

result.loc[weekend_blocked, "Final_Block_Reason"] = result.loc[
    weekend_blocked,
    "Weekend_Block_Reason"
]

result.loc[result["Final_Trade_Allowed"] == True, "Final_Block_Reason"] = "TRADE_ALLOWED"

result.to_csv(OUT)

print("=" * 70)
print("Rows:", len(result))

print("\n===== WEEKEND GUARD =====")
print("Weekend Block:", result["Weekend_Block"].sum())
print("Weekend Trade Allowed:", result["Weekend_Trade_Allowed"].sum())

print("\nWeekend Block Reasons:")
print(result["Weekend_Block_Reason"].value_counts(dropna=False))

print("\n===== CONFIDENCE + SESSION + WEEKEND =====")
print("Confidence Approved:", result["Confidence_Approved"].sum())

session_ok = (
    (result["Session_Trade_Allowed"] == True)
    | (result["London_Trade_Allowed"] == True)
    | (result["NewYork_Trade_Allowed"] == True)
)

print("Session OK:", session_ok.sum())
print("Final Trade Allowed:", result["Final_Trade_Allowed"].sum())

print("\nFinal Block Reasons:")
print(result["Final_Block_Reason"].value_counts(dropna=False).head(20))

final_trades = result[result["Final_Trade_Allowed"] == True].copy()

print("\nFinal Trade Preview:")
if len(final_trades) > 0:
    print(
        final_trades[
            [
                "Close",
                "Trade_Direction",
                "Setup_Score",
                "Confidence_Score",
                "Confidence_Label",
                "Session_Name",
                "Killzone",
                "Weekend_Block",
                "Weekend_Block_Reason",
                "Final_Trade_Allowed",
                "Setup_ID",
            ]
        ].tail(20)
    )
else:
    print("No final trades allowed")

print("\n===== FRIDAY / MONDAY CHECK =====")

check_rows = result[
    (result.index.weekday.isin([0, 4, 5, 6]))
][
    [
        "Close",
        "Session_Name",
        "Weekend_Block",
        "Weekend_Block_Reason",
        "Weekend_Trade_Allowed",
        "Confidence_Approved",
        "Final_Trade_Allowed",
    ]
]

print(check_rows.tail(40))

print("\nLatest Weekend Status:")
print(weekend_guard.get_latest_status(result))

print("=" * 70)
print(f"Saved: {OUT}")
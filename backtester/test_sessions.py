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


DATA = ROOT / "data" / "raw" / "XAUUSD_M15.csv"
OUT = ROOT / "data" / "processed" / "XAUUSD_M15_sessions_result.csv"

OUT.parent.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(DATA)
df["Time"] = pd.to_datetime(df["Time"])
df.set_index("Time", inplace=True)

# Detection pipeline
df = MarketStructureDetector().process_structure(df)
df = LiquidityEngine().process_liquidity(df)
df = FVGDetector().process_fvg(df)
df = OrderBlockEngine().process_order_blocks(df)
df = VolumeImbalanceDetector().process_volume_imbalance(df)
df = LiquidityVoidDetector().process_liquidity_void(df)
df = PremiumDiscountDetector().process_premium_discount(df)
df = SupportResistanceDetector().process_support_resistance(df)
df = CandlePatternDetector().process_candle_patterns(df)

# Scoring pipeline
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

# Sessions pipeline
df = KillzoneEngine().process_killzones(df)
df = LondonSessionEngine().process_london_session(df)
result = NewYorkSessionEngine().process_newyork_session(df)

result.to_csv(OUT)

print("=" * 70)
print("Rows:", len(result))

print("\n===== KILLZONES =====")
print("In Killzone:", result["In_Killzone"].sum())
print("Session Trade Allowed:", result["Session_Trade_Allowed"].sum())
print("Best Trading Window:", result["Best_Trading_Window"].sum())

print("\nSession Names:")
print(result["Session_Name"].value_counts(dropna=False))

print("\nKillzones:")
print(result["Killzone"].value_counts(dropna=False))

print("\n===== LONDON =====")
print("London Active:", result["London_Active"].sum())
print("London Trade Allowed:", result["London_Trade_Allowed"].sum())
print("London Swept Asian High:", result["London_Swept_Asian_High"].sum())
print("London Swept Asian Low:", result["London_Swept_Asian_Low"].sum())

print("\nLondon Bias:")
print(result["London_Bias"].value_counts(dropna=False))

print("\n===== NEW YORK =====")
print("NewYork Active:", result["NewYork_Active"].sum())
print("NewYork Trade Allowed:", result["NewYork_Trade_Allowed"].sum())
print("NewYork Swept London High:", result["NewYork_Swept_London_High"].sum())
print("NewYork Swept London Low:", result["NewYork_Swept_London_Low"].sum())
print("NewYork Swept Asian High:", result["NewYork_Swept_Asian_High"].sum())
print("NewYork Swept Asian Low:", result["NewYork_Swept_Asian_Low"].sum())

print("\nNewYork Bias:")
print(result["NewYork_Bias"].value_counts(dropna=False))

print("\n===== CONFIDENCE + SESSION FILTER =====")
tradeable = result[result["Confidence_Approved"] == True].copy()

print("Confidence Approved Before Session Filter:", len(tradeable))

if len(tradeable) > 0:
    tradeable_session_ok = tradeable[
        (tradeable["Session_Trade_Allowed"] == True)
        | (tradeable["London_Trade_Allowed"] == True)
        | (tradeable["NewYork_Trade_Allowed"] == True)
    ]

    print("Tradeable With Session OK:", len(tradeable_session_ok))

    print("\nTradeable Session Preview:")
    print(
        tradeable_session_ok[
            [
                "Close",
                "Trade_Direction",
                "Setup_Score",
                "Confidence_Score",
                "Confidence_Label",
                "Session_Name",
                "Killzone",
                "London_Bias",
                "NewYork_Bias",
                "Session_Strength",
                "London_Strength",
                "NewYork_Strength",
                "Setup_ID",
            ]
        ].tail(20)
    )
else:
    print("No confidence-approved setups found")

print("\n===== LATEST SESSION SNAPSHOT =====")
print("Killzone:", KillzoneEngine().get_latest_session(result))
print("London:", LondonSessionEngine().get_latest_london(result))
print("NewYork:", NewYorkSessionEngine().get_latest_newyork(result))

print("=" * 70)
print(f"Saved: {OUT}")
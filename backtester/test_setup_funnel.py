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

from core_engine.filters.htf_bias_filter import HTFBiasFilter
from core_engine.filters.htf_score_modifier import HTFScoreModifier

from core_engine.sessions.killzones import KillzoneEngine
from core_engine.sessions.london_session import LondonSessionEngine
from core_engine.sessions.newyork_session import NewYorkSessionEngine
from core_engine.risk.weekend_guard import WeekendGuard


DATA = ROOT / "data" / "raw" / "XAUUSD_M15.csv"


def load_mt5_csv(path):
    df = pd.read_csv(path, sep="\t")

    df.columns = [
        c.replace("<", "").replace(">", "").strip().title()
        for c in df.columns
    ]

    df.rename(columns={
        "Time": "Clock",
        "Tickvol": "TickVolume",
        "Vol": "Volume",
    }, inplace=True)

    df["Time"] = pd.to_datetime(df["Date"].astype(str) + " " + df["Clock"].astype(str))
    df = df[["Time", "Open", "High", "Low", "Close", "TickVolume", "Volume", "Spread"]]
    df.set_index("Time", inplace=True)

    for col in ["Open", "High", "Low", "Close", "TickVolume", "Volume", "Spread"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df.dropna()


def count_true(df, col):
    if col not in df.columns:
        return "NOT_FOUND"
    return int(df[col].fillna(False).sum())


print("=" * 70)
print("SETUP FUNNEL ANALYSIS - FULL RAW PIPELINE")
print("=" * 70)

df = load_mt5_csv(DATA)

print("Raw Candles:", len(df))

df = MarketStructureDetector().process_structure(df)
df = LiquidityEngine().process_liquidity(df)
df = FVGDetector().process_fvg(df)
df = OrderBlockEngine().process_order_blocks(df)
df = VolumeImbalanceDetector().process_volume_imbalance(df)
df = LiquidityVoidDetector().process_liquidity_void(df)
df = PremiumDiscountDetector().process_premium_discount(df)
df = SupportResistanceDetector().process_support_resistance(df)
df = CandlePatternDetector().process_candle_patterns(df)

df = ScoreEngine().process_score(df)

df = HTFBiasFilter(
    htf_timeframe="1h",
    require_htf_bias=False,
    allow_neutral=True,
).process_htf_bias(df)

df = HTFScoreModifier(
    aligned_bonus=5.0,
    opposite_penalty=8.0,
    neutral_modifier=0.0,
    score_column="Setup_Score",
    output_column="Setup_Score",
).process_htf_score(df)

df = SetupRanker(
    min_score=65,
    premium_score=78,
    max_daily_setups=5,
    min_daily_setups_target=3,
    cooldown_candles=3,
    max_same_direction_per_day=3,
    require_mss_or_choch=False,
    require_liquidity=True,
    require_fvg_or_ob=True
).process_rankings(df)

df = ConfidenceScoreEngine(
    min_confidence=50,
    premium_confidence=70,
    elite_confidence=85,
    max_confidence=98
).process_confidence(df)

df = KillzoneEngine().process_killzones(df)
df = LondonSessionEngine().process_london_session(df)
df = NewYorkSessionEngine().process_newyork_session(df)

df = WeekendGuard(
    friday_cutoff_hour=19,
    monday_resume_hour=10,
    block_weekend=True
).process_weekend_guard(df)

candidate_rows = df[
    (df["Confidence_Approved"] == True)
    & (
        (df["Session_Trade_Allowed"] == True)
        | (df["London_Trade_Allowed"] == True)
        | (df["NewYork_Trade_Allowed"] == True)
    )
    & (df["Weekend_Trade_Allowed"] == True)
].copy()

print("\n===== SIGNAL COUNTS =====")
for col in [
    "MSS",
    "CHoCH",
    "BOS",
    "Liquidity_Sweep",
    "Valid_Sweep",
    "Bullish_FVG",
    "Bearish_FVG",
    "Bullish_OB",
    "Bearish_OB",
    "OB_Valid",
    "Active_OB_Valid",
    "FVG_Valid",
    "Active_FVG_Valid",
]:
    print(f"{col}: {count_true(df, col)}")

print("\n===== FUNNEL COUNTS =====")
print("Setup_Approved:", count_true(df, "Setup_Approved"))
print("Confidence_Approved:", count_true(df, "Confidence_Approved"))
print("Session_Trade_Allowed:", count_true(df, "Session_Trade_Allowed"))
print("London_Trade_Allowed:", count_true(df, "London_Trade_Allowed"))
print("NewYork_Trade_Allowed:", count_true(df, "NewYork_Trade_Allowed"))
print("Weekend_Trade_Allowed:", count_true(df, "Weekend_Trade_Allowed"))
print("Final Candidate Rows:", len(candidate_rows))

print("\n===== REJECT REASONS =====")
if "Setup_Reject_Reason" in df.columns:
    print(df["Setup_Reject_Reason"].value_counts(dropna=False).head(30))

print("\n===== SETUP RANK =====")
if "Setup_Rank" in df.columns:
    print(df["Setup_Rank"].value_counts(dropna=False))

print("\n===== SETUP SCORE STATS =====")
print(df["Setup_Score"].describe())

print("\n===== CONFIDENCE SCORE STATS =====")
print(df["Confidence_Score"].describe())

print("=" * 70)
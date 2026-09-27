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


RAW_FILE = ROOT / "data" / "raw" / "BTCUSDm_M15.csv"
REJECT_FILE = ROOT / "data" / "processed" / "BTCUSDm_reject_breakdown.csv"


def load_mt5_csv(path):
    df = pd.read_csv(path, sep="\t")
    df.columns = [c.replace("<", "").replace(">", "").strip().title() for c in df.columns]
    df.rename(columns={"Time": "Clock", "Tickvol": "TickVolume", "Vol": "Volume"}, inplace=True)
    df["Time"] = pd.to_datetime(df["Date"].astype(str) + " " + df["Clock"].astype(str), errors="coerce")
    df = df[["Time", "Open", "High", "Low", "Close", "TickVolume", "Volume", "Spread"]]
    df.set_index("Time", inplace=True)
    return df.apply(pd.to_numeric, errors="coerce").dropna()


def process_pipeline(df):
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

    df = SetupRanker(
        min_score=68,
        premium_score=80,
        max_daily_setups=3,
        min_daily_setups_target=1,
        cooldown_candles=12,
        max_same_direction_per_day=1,
        require_mss_or_choch=False,
        require_liquidity=True,
        require_fvg_or_ob=True,
        prefer_best_setups=True,
    ).process_rankings(df)

    df = ConfidenceScoreEngine(
        min_confidence=50,
        premium_confidence=70,
        elite_confidence=85,
        max_confidence=98,
    ).process_confidence(df)

    df = KillzoneEngine().process_killzones(df)
    df = LondonSessionEngine().process_london_session(df)
    df = NewYorkSessionEngine().process_newyork_session(df)

    df = WeekendGuard(
        friday_cutoff_hour=19,
        monday_resume_hour=10,
        block_weekend=True,
    ).process_weekend_guard(df)

    return df


rejects = pd.read_csv(REJECT_FILE)
rejects = rejects[rejects["reason"] == "TRADE_QUALITY_SL_TOO_WIDE"].copy()
rejects["time"] = pd.to_datetime(rejects["time"])

df = process_pipeline(load_mt5_csv(RAW_FILE))

df = df.copy()
df.index.name = "Pipeline_Time"
df = df.reset_index()
df["Time"] = pd.to_datetime(df["Pipeline_Time"])

merged = rejects.merge(
    df,
    left_on="time",
    right_on="Time",
    how="left"
)

cols = [
    "time",
    "Trade_Direction",
    "Setup_Score",
    "Confidence_Score",
    "ATR",
    "Active_OB_Type",
    "Active_FVG_Type",
    "Active_OB_Upper",
    "Active_OB_Lower",
    "Active_FVG_Upper",
    "Active_FVG_Lower",
    "Setup_Rank",
    "Setup_Approved",
]

cols = [c for c in cols if c in merged.columns]

print("=" * 70)
print("BTC SL TOO WIDE ANALYSIS")
print("=" * 70)
print("SL_TOO_WIDE rejects:", len(merged))

print("\n===== FULL ANALYSIS =====")
print(merged[cols].to_string(index=False))

print("\n===== SCORE STATS =====")
print(merged[["Setup_Score", "Confidence_Score", "ATR"]].describe())

print("\n===== HIGH QUALITY REJECTS =====")
hq = merged[(merged["Setup_Score"] >= 80) & (merged["Confidence_Score"] >= 70)]
print("High quality count:", len(hq))
if len(hq) > 0:
    print(hq[cols].to_string(index=False))

OUT = ROOT / "data" / "processed" / "BTCUSDm_SL_TOO_WIDE_ANALYSIS.csv"
merged[cols].to_csv(OUT, index=False)

print("=" * 70)
print(f"Saved: {OUT}")
print("=" * 70)
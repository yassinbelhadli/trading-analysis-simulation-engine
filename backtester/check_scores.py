import sys, pandas as pd
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core_engine.config.detection.market_structure import MarketStructureDetector
from core_engine.config.detection.liquidity import LiquidityEngine
from core_engine.config.detection.fair_value_gap import FVGDetector
from core_engine.config.detection.order_blocks import OrderBlockEngine
from core_engine.config.detection.volume_imbalance import VolumeImbalanceDetector
from core_engine.config.detection.liquidity_void import LiquidityVoidDetector
from core_engine.config.detection.premium_discount import PremiumDiscountDetector
from core_engine.config.detection.support_resistance import SupportResistanceDetector
from core_engine.config.detection.candle_patterns import CandlePatternDetector
from core_engine.scoring.score_engine import ScoreEngine
from core_engine.scoring.setup_ranker import SetupRanker
from core_engine.scoring.confidence_score import ConfidenceScoreEngine
from core_engine.sessions.killzones import KillzoneEngine
from core_engine.sessions.london_session import LondonSessionEngine
from core_engine.sessions.newyork_session import NewYorkSessionEngine
from core_engine.risk.weekend_guard import WeekendGuard
from core_engine.filters.htf_bias_filter import HTFBiasFilter
from core_engine.filters.htf_score_modifier import HTFScoreModifier

for name, file in [("XAUUSD", "XAUUSD_M15.csv")]:
    print(f"\n=== {name} ===")
    fp = ROOT / "data" / "raw" / file
    if not fp.exists():
        print(f"  File not found: {fp}")
        continue
    df = pd.read_csv(fp, sep="\t")
    df.columns = [c.replace("<","").replace(">","").strip().title() for c in df.columns]
    df.rename(columns={"Date":"Date","Time":"Clock","Open":"Open","High":"High","Low":"Low",
        "Close":"Close","Tickvol":"TickVolume","Vol":"Volume","Spread":"Spread"}, inplace=True)
    df["Time"] = pd.to_datetime(df["Date"].astype(str) + " " + df["Clock"].astype(str))
    df = df[["Time","Open","High","Low","Close","TickVolume","Volume","Spread"]]
    df.set_index("Time", inplace=True)

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
    df = SetupRanker(min_score=50, premium_score=80, max_daily_setups=5, min_daily_setups_target=1,
        cooldown_candles=12, max_same_direction_per_day=1, require_mss_or_choch=False,
        require_liquidity=True, require_fvg_or_ob=True, prefer_best_setups=True).process_rankings(df)
    df = ConfidenceScoreEngine(min_confidence=50, premium_confidence=70,
        elite_confidence=85, max_confidence=98).process_confidence(df)
    df = HTFScoreModifier(aligned_bonus=5.0, opposite_penalty=8.0, neutral_modifier=0.0,
        score_column="Setup_Score", output_column="Setup_Score").process_htf_score(df)
    df = HTFBiasFilter(htf_timeframe="1h", swing_left=2, swing_right=2,
        bos_buffer_atr_mult=0.10, require_htf_bias=True, allow_neutral=True).process_htf_bias(df)
    df = KillzoneEngine().process_killzones(df)
    df = LondonSessionEngine().process_london_session(df)
    df = NewYorkSessionEngine().process_newyork_session(df)
    df = WeekendGuard(friday_cutoff_hour=19, monday_resume_hour=10, block_weekend=True).process_weekend_guard(df)

    approved = df[(df["Confidence_Approved"] == True) & (df["Weekend_Trade_Allowed"] == True)]
    session_ok = (approved["Session_Trade_Allowed"] == True) | (approved["London_Trade_Allowed"] == True) | (approved["NewYork_Trade_Allowed"] == True)
    approved = approved[session_ok]

    print(f"Total approved candidates: {len(approved)}")
    print(f"Score range: {approved['Setup_Score'].min():.0f} - {approved['Setup_Score'].max():.0f}")
    print(f"Unique days: {len(set(d.date() for d in approved.index))}")

    bins = [50, 65, 75, 85, 100]
    labels = ["50-64", "65-74", "75-84", "85+"]
    approved["score_bin"] = pd.cut(approved["Setup_Score"], bins=bins, labels=labels, right=False)
    print(approved["score_bin"].value_counts().sort_index())

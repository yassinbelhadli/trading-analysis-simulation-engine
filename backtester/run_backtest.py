import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

import pandas as pd

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

from core_engine.backtesting.backtester import Backtester, MODES, ModeConfig
from core_engine.backtesting.statistics import compute_stats

DATA_DIR = ROOT / "data" / "raw"
OUT_DIR = ROOT / "data" / "processed"

SYMBOLS = [
    ("XAUUSD (Gold)", "XAUUSD_M15.csv", "XAUUSD"),
    ("NAS100",        "USTEC_M15.csv", "USTEC"),
    ("BTCUSD",        "BTCUSDm_M15.csv", "BTCUSD"),
]


def load_data(filepath):
    df = pd.read_csv(filepath, sep="\t")
    df.columns = [c.replace("<", "").replace(">", "").strip().title() for c in df.columns]
    df.rename(columns={
        "Date": "Date", "Time": "Clock", "Open": "Open", "High": "High",
        "Low": "Low", "Close": "Close", "Tickvol": "TickVolume",
        "Vol": "Volume", "Spread": "Spread",
    }, inplace=True)
    df["Time"] = pd.to_datetime(df["Date"].astype(str) + " " + df["Clock"].astype(str))
    df = df[["Time", "Open", "High", "Low", "Close", "TickVolume", "Volume", "Spread"]]
    df.set_index("Time", inplace=True)
    return df


def run_detection_pipeline(df):
    print("  Running detection pipeline...", end=" ", flush=True)
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
        min_score=50, premium_score=80, max_daily_setups=5,
        min_daily_setups_target=1, cooldown_candles=12,
        max_same_direction_per_day=1, require_mss_or_choch=False,
        require_liquidity=True, require_fvg_or_ob=True, prefer_best_setups=True
    ).process_rankings(df)
    df = ConfidenceScoreEngine(
        min_confidence=50, premium_confidence=70,
        elite_confidence=85, max_confidence=98
    ).process_confidence(df)
    df = HTFScoreModifier(
        aligned_bonus=5.0, opposite_penalty=8.0, neutral_modifier=0.0,
        score_column="Setup_Score", output_column="Setup_Score",
    ).process_htf_score(df)
    df = HTFBiasFilter(
        htf_timeframe="1h", swing_left=2, swing_right=2,
        bos_buffer_atr_mult=0.10, require_htf_bias=True, allow_neutral=True,
    ).process_htf_bias(df)
    df = KillzoneEngine().process_killzones(df)
    df = LondonSessionEngine().process_london_session(df)
    df = NewYorkSessionEngine().process_newyork_session(df)
    df = WeekendGuard(
        friday_cutoff_hour=19, monday_resume_hour=10, block_weekend=True
    ).process_weekend_guard(df)
    print("OK")
    return df


SEP = "=" * 90
print(SEP)
print("BACKTEST - ALL MODES x ALL SYMBOLS")
print(SEP)

all_stats = []
backtester = Backtester(account_balance=10000, risk_per_trade=0.005)

for label, file, name in SYMBOLS:
    print(f"\n{SEP}")
    print(f"SYMBOL: {label}")
    print(SEP)

    fp = DATA_DIR / file
    if not fp.exists():
        print(f"  File not found: {fp}")
        continue

    df = load_data(fp)
    df = run_detection_pipeline(df)

    for mode in MODES:
        print(f"  Mode: {mode.label} (score>={mode.min_score}, max {mode.max_trades_per_day}/day)")
        trades = backtester.run_mode(df, mode, name)
        if not trades:
            print(f"    -> No trades")
            continue

        stats = compute_stats(trades, mode.label, name)
        all_stats.append(stats)

        print(f"    -> {stats.total_trades} trades | WR: {stats.win_rate}% | PF: {stats.profit_factor} | "
              f"PnL: ${stats.net_pnl} | Exp: ${stats.expectancy} | AvgRR: {stats.avg_rr}")

        csv_path = OUT_DIR / f"{name}_{mode.name}_backtest.csv"
        pd.DataFrame([t.__dict__ for t in trades]).to_csv(csv_path, index=False)

Backtester.print_summary(all_stats)

if all_stats:
    summary_rows = []
    for s in all_stats:
        summary_rows.append({
            "Symbol": s.symbol, "Mode": s.mode,
            "Trades": s.total_trades, "WR%": s.win_rate,
            "PF": s.profit_factor, "Net PnL": s.net_pnl,
            "Expectancy": s.expectancy, "Avg RR": s.avg_rr,
            "Avg Win PnL": s.avg_win_pnl, "Avg Loss PnL": s.avg_loss_pnl,
            "Max Loss Streak": s.max_consecutive_losses,
            "Max Win Streak": s.max_consecutive_wins,
            "Trades/Day": s.trades_per_day,
            "Candles Held": s.avg_candles_held,
        })
    pd.DataFrame(summary_rows).to_csv(OUT_DIR / "full_backtest_summary.csv", index=False)
    print(f"\nSaved: {OUT_DIR / 'full_backtest_summary.csv'}")

print(f"\n{SEP}")
print("DONE")
print(SEP)

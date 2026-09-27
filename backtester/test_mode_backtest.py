import pandas as pd
import numpy as np
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

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

DATA_DIR = ROOT / "data" / "raw"
OUT_DIR = ROOT / "data" / "processed"
OUT_DIR.mkdir(parents=True, exist_ok=True)

MODES = [
    {"name": "ULTRA_CONSERVATIVE", "label": "Ultra Conservative", "min_score": 85, "max_trades": 2, "min_rr": 2.0},
    {"name": "CONSERVATIVE",       "label": "Conservative",      "min_score": 75, "max_trades": 3, "min_rr": 1.8},
    {"name": "BALANCED",           "label": "Balanced",          "min_score": 65, "max_trades": 5, "min_rr": 1.5},
    {"name": "AGGRESSIVE",         "label": "Aggressive",        "min_score": 50, "max_trades": 10, "min_rr": 1.5},
]

SYMBOLS = [
    {"file": "XAUUSD_M15.csv",      "name": "XAUUSD", "label": "XAUUSD (Gold)"},
    {"file": "USTEC_M15.csv",       "name": "USTEC",  "label": "NAS100"},
    {"file": "BTCUSDm_M15.csv",     "name": "BTCUSD", "label": "BTCUSD"},
]

CONTRACT_SIZES = {"XAUUSD": 100, "USTEC": 100, "BTCUSD": 1}
SEP = "=" * 80


def load_data(filepath):
    df = pd.read_csv(filepath, sep="\t")
    df.columns = [c.replace("<","").replace(">","").strip().title() for c in df.columns]
    df.rename(columns={"Date":"Date","Time":"Clock","Open":"Open","High":"High","Low":"Low",
        "Close":"Close","Tickvol":"TickVolume","Vol":"Volume","Spread":"Spread"}, inplace=True)
    df["Time"] = pd.to_datetime(df["Date"].astype(str) + " " + df["Clock"].astype(str))
    df = df[["Time","Open","High","Low","Close","TickVolume","Volume","Spread"]]
    df.set_index("Time", inplace=True)
    return df


def process_detection(df):
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
    df = SetupRanker(min_score=50, premium_score=80, max_daily_setups=5,
        min_daily_setups_target=1, cooldown_candles=12, max_same_direction_per_day=1,
        require_mss_or_choch=False, require_liquidity=True, require_fvg_or_ob=True,
        prefer_best_setups=True).process_rankings(df)
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
    return df


def get_candidates(df, min_score):
    session_ok = (
        (df["Session_Trade_Allowed"] == True)
        | (df["London_Trade_Allowed"] == True)
        | (df["NewYork_Trade_Allowed"] == True)
    )
    cand = df[
        (df["Confidence_Approved"] == True) & session_ok
        & (df["Weekend_Trade_Allowed"] == True)
        & (df["Setup_Score"] >= min_score)
    ].copy()
    return cand


def compute_atr(df, window=14):
    high = df["High"].astype(float)
    low = df["Low"].astype(float)
    close = df["Close"].astype(float)
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(window).mean()


def simulate_trade(row, idx, df, symbol, min_rr):
    direction = "BUY" if row.get("Direction") == "BUY" else "SELL"
    entry_price = float(row["Close"])
    atr = compute_atr(df.loc[:idx])
    current_atr = float(atr.iloc[-1]) if len(atr) > 0 else float(row["High"]) - float(row["Low"])

    sl_atr_mult = 0.8 if symbol == "BTCUSD" else 0.5
    tp_rr = max(min_rr, 2.0)

    if direction == "BUY":
        sl = entry_price - current_atr * sl_atr_mult
        tp = entry_price + (entry_price - sl) * tp_rr
    else:
        sl = entry_price + current_atr * sl_atr_mult
        tp = entry_price - (sl - entry_price) * tp_rr

    cs = CONTRACT_SIZES.get(symbol, 100)
    risk_balance = 10000 * 0.01  # 1% risk per trade
    risk_per_unit = abs(entry_price - sl)
    lot = round(risk_balance / (risk_per_unit * cs), 2) if risk_per_unit > 0 else 0.01
    lot = max(0.01, min(lot, 10.0))

    be_moved = False
    partial_done = False
    partial_pnl = 0.0
    current_sl = sl

    future = df[df.index > idx].head(200)

    for ts, candle in future.iterrows():
        high = float(candle["High"])
        low = float(candle["Low"])
        close = float(candle["Close"])

        if direction == "BUY":
            risk = entry_price - sl
            r_mult = (close - entry_price) / risk if risk > 0 else 0

            if not be_moved and r_mult >= 1.0:
                be_moved = True
                current_sl = entry_price

            if not partial_done and r_mult >= 0.75:
                partial_done = True
                partial_pnl = (lot * 0.5) * cs * (close - entry_price)

            if high >= tp:
                pnl = lot * cs * (tp - entry_price)
                return ("TP_HIT", "TP_HIT", round(tp, 2), round(pnl, 2),
                        be_moved, partial_done, round(partial_pnl, 2))
            if low <= current_sl:
                pnl = lot * cs * (current_sl - entry_price)
                return ("SL_HIT", "SL_HIT", round(current_sl, 2), round(pnl, 2),
                        be_moved, partial_done, round(partial_pnl, 2))

        else:
            risk = sl - entry_price
            r_mult = (entry_price - close) / risk if risk > 0 else 0

            if not be_moved and r_mult >= 1.0:
                be_moved = True
                current_sl = entry_price

            if not partial_done and r_mult >= 0.75:
                partial_done = True
                partial_pnl = (lot * 0.5) * cs * (entry_price - close)

            if low <= tp:
                pnl = lot * cs * (entry_price - tp)
                return ("TP_HIT", "TP_HIT", round(tp, 2), round(pnl, 2),
                        be_moved, partial_done, round(partial_pnl, 2))
            if high >= current_sl:
                pnl = lot * cs * (entry_price - current_sl)
                return ("SL_HIT", "SL_HIT", round(current_sl, 2), round(pnl, 2),
                        be_moved, partial_done, round(partial_pnl, 2))

    return ("OPEN", "TIMEOUT", round(entry_price, 2), 0.0, be_moved, partial_done, 0.0)


print(SEP)
print("MULTI-MODE BACKTEST - ALL SYMBOLS x ALL MODES (Direct)")
print(SEP)

all_rows = []

for sym in SYMBOLS:
    print(f"\n{SEP}")
    print(f"LOADING: {sym['label']}")
    print(SEP)
    fp = DATA_DIR / sym["file"]
    if not fp.exists():
        print(f"  SKIP - file not found: {fp}")
        continue

    print("  Detection pipeline...")
    df = load_data(fp)
    df = process_detection(df)
    print(f"  Total candles: {len(df)}")

    atr_series = compute_atr(df)

    for mode in MODES:
        print(f"\n  --- {mode['label']} (score>={mode['min_score']}, max {mode['max_trades']}/day, RR>={mode['min_rr']}) ---")
        candidates = get_candidates(df, mode["min_score"])

        if len(candidates) == 0:
            print("  -> No candidates")
            continue

        trades_data = []
        daily_count = {}
        daily_rr = {}

        for idx, row in candidates.iterrows():
            day_key = str(idx.date())
            if daily_count.get(day_key, 0) >= mode["max_trades"]:
                continue

            direction = row.get("Direction", "BUY")
            score = row["Setup_Score"]

            # Skip if RR check fails (estimate from ATR)
            atr_val = float(atr_series.loc[idx]) if idx in atr_series.index else 1.0
            risk_points = atr_val * 0.5
            if risk_points <= 0:
                continue
            close_price = float(row["Close"])
            est_rr = (risk_points * 2.0) / risk_points if direction == "BUY" else (risk_points * 2.0) / risk_points
            if est_rr < mode["min_rr"]:
                continue

            status, close_reason, close_price, pnl, be_moved, partial_done, partial_pnl = \
                simulate_trade(row, idx, df, sym["name"], mode["min_rr"])

            daily_count[day_key] = daily_count.get(day_key, 0) + 1
            entry_price = float(row["Close"])

            trades_data.append({
                "trade_id": f"{mode['name']}_{sym['name']}_{len(trades_data)+1}",
                "symbol": sym["name"],
                "mode": mode["label"],
                "direction": direction,
                "lot_size": 0.01,
                "entry_price": entry_price,
                "score": score,
                "status": status,
                "close_reason": close_reason,
                "close_price": close_price,
                "pnl_money": pnl,
                "partial_pnl": partial_pnl,
                "total_pnl": round(pnl + partial_pnl, 2),
                "be_moved": be_moved,
                "partial_closed": partial_done,
                "open_time": str(idx),
            })

        df_trades = pd.DataFrame(trades_data)
        if len(df_trades) == 0:
            print("  -> No trades executed")
            continue

        total = len(df_trades)
        tp_wins = len(df_trades[df_trades["status"] == "TP_HIT"])
        sl_losses = len(df_trades[df_trades["status"] == "SL_HIT"])
        open_trades = len(df_trades[df_trades["status"] == "OPEN"])
        be_count = df_trades["be_moved"].sum()
        partial_count = df_trades["partial_closed"].sum()
        total_pnl = df_trades["total_pnl"].sum()

        winrate = round(tp_wins / total * 100, 2) if total > 0 else 0
        gross_profit = df_trades[df_trades["total_pnl"] > 0]["total_pnl"].sum()
        gross_loss = abs(df_trades[df_trades["total_pnl"] < 0]["total_pnl"].sum())
        profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else (float('inf') if gross_profit > 0 else 0)
        expectancy = round(total_pnl / total, 2) if total > 0 else 0

        print(f"  -> {total} trades (C:{len(candidates)}) | WR: {winrate}% | PF: {profit_factor} | Net: ${round(total_pnl, 2)} | Exp: ${expectancy}")

        all_rows.append({
            "Symbol": sym["label"],
            "Mode": mode["label"],
            "Score>=": mode["min_score"],
            "Candidates": len(candidates),
            "Trades": total,
            "TP": tp_wins,
            "SL": sl_losses,
            "Open": open_trades,
            "BE": int(be_count),
            "Partial": int(partial_count),
            "Win Rate": f"{winrate}%",
            "Profit Factor": profit_factor if profit_factor != float('inf') else "INF",
            "Total PnL": round(total_pnl, 2),
            "Expectancy": expectancy,
        })

        out_csv = OUT_DIR / f"{sym['name']}_{mode['name']}_bt_result.csv"
        df_trades.to_csv(out_csv, index=False)

if all_rows:
    summary = pd.DataFrame(all_rows)
    print(f"\n{SEP}")
    print("SUMMARY TABLE")
    print(SEP)
    cols = ["Symbol", "Mode", "Trades", "Win Rate", "Profit Factor", "Total PnL", "Expectancy"]
    print(summary[cols].to_string(index=False))

    summary.to_csv(OUT_DIR / "mode_backtest_direct_summary.csv", index=False)
    print(f"\nSaved results.")

print("\nDONE.")

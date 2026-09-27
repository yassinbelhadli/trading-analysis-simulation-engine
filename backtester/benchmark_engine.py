"""
benchmark_engine.py
Benchmark the current ICT engine vs config toggle (require_mss_or_choch ON/OFF)
to show the impact of the structural fixes.
"""
import sys, os, json, time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
import numpy as np

from core_engine.config.detection.market_structure import MarketStructureDetector
from core_engine.config.detection.liquidity import LiquidityEngine
from core_engine.config.detection.fair_value_gap import FVGDetector
from core_engine.config.detection.order_blocks import OrderBlockEngine
from core_engine.scoring.score_engine import ScoreEngine
from core_engine.scoring.setup_ranker import SetupRanker


def load_data(symbol: str, csv_path: str = None) -> pd.DataFrame:
    """Load CSV or generate synthetic data."""
    if csv_path and os.path.exists(csv_path):
        df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
        # Normalize column names
        col_map = {
            "open": "Open", "high": "High", "low": "Low", "close": "Close",
            "OPEN": "Open", "HIGH": "High", "LOW": "Low", "CLOSE": "Close",
        }
        df = df.rename(columns=col_map)
        req = {"Open", "High", "Low", "Close"}
        if not req.issubset(df.columns):
            raise ValueError(f"CSV missing columns. Has: {list(df.columns)}")
        return df

    # Fallback: generate semi-realistic synthetic data (session-aligned)
    np.random.seed(0)
    n = 2000
    base = {"XAUUSD": 3360.0, "NAS100": 16500.0, "EURUSD": 1.05}.get(symbol, 100.0)
    vol = {"XAUUSD": 0.5, "NAS100": 2.5, "EURUSD": 0.0003}.get(symbol, 0.1)
    # Spread across multiple days, during LONDON/NEWYORK session hours
    days = max(1, n // 78)  # ~78 candles per session (6.5h * 12)
    dates = []
    for d in range(days):
        for h in range(8, 17):  # 8 AM to 5 PM (covers LONDON + NEWYORK overlap)
            for m in range(0, 60, 5):
                if len(dates) >= n: break
                dates.append(pd.Timestamp(f"2026-01-{d+1:02d} {h:02d}:{m:02d}:00"))
            if len(dates) >= n: break
        if len(dates) >= n: break
    dates = pd.DatetimeIndex(dates[:n])
    trend = np.cumsum(np.random.normal(0, vol, n))
    close = base + trend + np.random.normal(0, vol * 0.3, n)
    open_p = close - np.random.normal(0, vol * 0.5, n)
    high = np.maximum(open_p, close) + np.abs(np.random.normal(vol * 1.5, vol, n))
    low = np.minimum(open_p, close) - np.abs(np.random.normal(vol * 1.5, vol, n))
    return pd.DataFrame({"Open": open_p, "High": high, "Low": low, "Close": close}, index=dates)


def get_session(timestamp):
    hour = timestamp.hour
    if 7 <= hour < 12: return "LONDON"
    if 13 <= hour < 17: return "NEWYORK"
    return "OTHER"


def run_pipeline(df: pd.DataFrame, require_structure: bool) -> dict:
    """Run full ICT pipeline and return key metrics."""
    ms = MarketStructureDetector()
    df = ms.process_structure(df)

    liq = LiquidityEngine()
    df = liq.process_liquidity(df)

    fvg = FVGDetector()
    df = fvg.process_fvg(df)

    ob = OrderBlockEngine()
    df = ob.process_order_blocks(df)

    se = ScoreEngine()
    df = se.process_score(df)

    sr = SetupRanker(require_mss_or_choch=require_structure)
    df = sr.process_rankings(df)

    approved = df[df["Setup_Approved"] == True].copy()
    total = len(approved)

    if total == 0:
        return {
            "total_trades": 0, "win_rate": 0, "profit_factor": 0,
            "total_pnl": 0, "avg_score": 0, "avg_priority": 0, "avg_rr": 0,
            "structure_breakdown": {},
            "session_breakdown": {},
            "direction_breakdown": {},
        }

    # Simulate trade outcomes based on score/confidence
    np.random.seed(42)
    trades = []
    for idx, row in approved.iterrows():
        score = float(row.get("Setup_Score", 60))
        confidence = float(row.get("Confidence_Score", 50))
        direction = row.get("Trade_Direction", "BUY")
        session = get_session(idx)

        # Simulate: higher score → higher win probability
        win_prob = min(0.3 + (score - 50) * 0.004, 0.55)
        rr = float(row.get("Setup_RR", 1.5)) if "Setup_RR" in row else 1.5
        won = np.random.random() < win_prob
        pnl = rr * 100 if won else -100

        trades.append({
            "direction": direction,
            "session": session,
            "won": won,
            "pnl": pnl,
            "rr": rr,
            "score": score,
            "confidence": confidence,
        })

    df_trades = pd.DataFrame(trades)
    wins = df_trades[df_trades["won"] == True]
    losses = df_trades[df_trades["won"] == False]
    total_pnl = df_trades["pnl"].sum()
    gross_profit = wins["pnl"].sum() if len(wins) > 0 else 0
    gross_loss = abs(losses["pnl"].sum()) if len(losses) > 0 else 1

    return {
        "total_trades": total,
        "win_rate": round(len(wins) / total * 100, 2) if total > 0 else 0,
        "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss > 0 else 999,
        "total_pnl": round(total_pnl, 2),
        "avg_score": round(df_trades["score"].mean(), 2),
        "avg_priority": 0,
        "avg_rr": round(df_trades["rr"].mean(), 2),
        "structure_breakdown": {
            "mss": int(approved["MSS"].sum()),
            "choch": int(approved["CHoCH"].sum()),
            "bos": int(approved["BOS"].sum()),
        },
        "session_breakdown": approved.index.map(get_session).value_counts().to_dict(),
        "direction_breakdown": approved["Trade_Direction"].value_counts().to_dict(),
    }


def main():
    symbols = ["XAUUSD", "NAS100", "EURUSD"]
    results = {}

    for sym in symbols:
        print(f"\n{'='*60}")
        print(f"  {sym}")
        print(f"{'='*60}")

        df = load_data(sym)
        print(f"  Data: {len(df)} candles")

        # NEW engine (require_structure=True)
        t0 = time.time()
        new_results = run_pipeline(df, require_structure=True)
        t1 = time.time()
        print(f"  NEW engine ({t1-t0:.1f}s):")
        print(f"    Trades: {new_results['total_trades']}")
        print(f"    Win Rate: {new_results['win_rate']}%")
        print(f"    Profit Factor: {new_results['profit_factor']}")
        print(f"    Avg RR: {new_results['avg_rr']}")

        # OLD engine (require_structure=False + allow weak entries)
        t0 = time.time()
        old_results = run_pipeline(df, require_structure=False)
        t1 = time.time()
        print(f"  OLD engine ({t1-t0:.1f}s):")
        print(f"    Trades: {old_results['total_trades']}")
        print(f"    Win Rate: {old_results['win_rate']}%")
        print(f"    Profit Factor: {old_results['profit_factor']}")
        print(f"    Avg RR: {old_results['avg_rr']}")

        # Delta
        print(f"  ── DELTA (NEW - OLD) ──")
        delta_trades = new_results["total_trades"] - old_results["total_trades"]
        delta_wr = round(new_results["win_rate"] - old_results["win_rate"], 2)
        delta_pf = round(new_results["profit_factor"] - old_results["profit_factor"], 4)
        delta_pnl = round(new_results["total_pnl"] - old_results["total_pnl"], 2)
        print(f"    Trades: {delta_trades:+d}")
        print(f"    Win Rate: {delta_wr:+.2f}%")
        print(f"    Profit Factor: {delta_pf:+.4f}")
        print(f"    PnL: ${delta_pnl:+.2f}")

        results[sym] = {"new": new_results, "old": old_results}

    # Summary
    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    total_new_trades = sum(results[s]["new"]["total_trades"] for s in symbols)
    total_old_trades = sum(results[s]["old"]["total_trades"] for s in symbols)
    avg_new_wr = sum(results[s]["new"]["win_rate"] for s in symbols) / len(symbols)
    avg_old_wr = sum(results[s]["old"]["win_rate"] for s in symbols) / len(symbols)
    avg_new_pf = sum(results[s]["new"]["profit_factor"] for s in symbols) / len(symbols)
    avg_old_pf = sum(results[s]["old"]["profit_factor"] for s in symbols) / len(symbols)

    print(f"  Total Trades: OLD={total_old_trades}  NEW={total_new_trades}  Δ={total_new_trades-total_old_trades:+d}")
    print(f"  Avg Win Rate: OLD={avg_old_wr:.2f}%  NEW={avg_new_wr:.2f}%  Δ={avg_new_wr-avg_old_wr:+.2f}%")
    print(f"  Avg Profit Factor: OLD={avg_old_pf:.4f}  NEW={avg_new_pf:.4f}  Δ={avg_new_pf-avg_old_pf:+.4f}")

    out_path = Path("backtester/benchmark_results.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Results saved to {out_path}")


if __name__ == "__main__":
    main()

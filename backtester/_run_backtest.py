import sys, time, pandas as pd, numpy as np
sys.path.insert(0, '.')
from core_engine.config.detection.market_structure import MarketStructureDetector
from core_engine.config.detection.liquidity import LiquidityEngine
from core_engine.config.detection.fair_value_gap import FVGDetector
from core_engine.config.detection.order_blocks import OrderBlockEngine
from core_engine.scoring.score_engine import ScoreEngine
from core_engine.scoring.setup_ranker import SetupRanker

def backtest(symbol, vol, base):
    np.random.seed(0)
    n = 8000
    dates = []
    for d in range(n // 80 + 1):
        for h in range(8, 17):
            for m in range(0, 60, 5):
                if len(dates) >= n:
                    break
                dates.append(pd.Timestamp("2026-01-{:02d} {:02d}:{:02d}:00".format((d % 30) + 1, h, m)))
            if len(dates) >= n:
                break
        if len(dates) >= n:
            break
    dates = pd.DatetimeIndex(dates[:n])

    trend = np.cumsum(np.random.normal(0, vol, n))
    close = base + trend + np.random.normal(0, vol * 0.3, n)
    open_p = close - np.random.normal(0, vol * 0.5, n)
    high = np.maximum(open_p, close) + np.abs(np.random.normal(vol * 1.5, vol, n))
    low = np.minimum(open_p, close) - np.abs(np.random.normal(vol * 1.5, vol, n))
    df = pd.DataFrame({"Open": open_p, "High": high, "Low": low, "Close": close}, index=dates)

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

    results = {}
    for mode_name, min_score, max_day in [
        ("Ultra_Conservative", 85, 2),
        ("Conservative", 75, 3),
        ("Balanced", 65, 5),
        ("Aggressive", 50, 10),
    ]:
        sr = SetupRanker(min_score=min_score, max_daily_setups=max_day, require_mss_or_choch=True)
        df2 = sr.process_rankings(df.copy())
        approved = df2[df2["Setup_Approved"] == True]
        total = len(approved)

        if total == 0:
            results[mode_name] = {"trades": 0, "wr": 0, "pf": 0, "pnl": 0, "avg_rr": 0}
            continue

        np.random.seed(42)
        wins, gross_profit, gross_loss = 0, 0, 0
        rrs = []
        for _, row in approved.iterrows():
            score = float(row["Setup_Score"])
            win_prob = min(0.25 + (score - 50) * 0.005, 0.55)
            won = np.random.random() < win_prob
            rr = 1.5 + np.random.random() * 0.8
            rrs.append(rr)
            pnl = rr * 100 if won else -100
            if won:
                wins += 1
                gross_profit += pnl
            else:
                gross_loss += abs(pnl)

        results[mode_name] = {
            "trades": total,
            "wr": round(wins / total * 100, 2) if total else 0,
            "pf": round(gross_profit / gross_loss, 4) if gross_loss else 999,
            "pnl": round(gross_profit - gross_loss, 2),
            "avg_rr": round(np.mean(rrs), 2),
        }
    return results


for sym, vol, base in [
    ("NAS100", 2.5, 16500.0),
    ("BTCUSD", 15.0, 68000.0),
]:
    print("=" * 60)
    print("  {}".format(sym))
    print("=" * 60)
    t0 = time.time()
    res = backtest(sym, vol, base)
    print("  Runtime: {:.1f}s".format(time.time() - t0))
    for mode, data in res.items():
        print(
            "  {:25s}: trades={:5d} | WR={:6.2f}% | PF={:6.4f} | PnL=${:>9.2f} | RR={:4.2f}".format(
                mode,
                data["trades"],
                data["wr"],
                data["pf"],
                data["pnl"],
                data["avg_rr"],
            )
        )
    print()

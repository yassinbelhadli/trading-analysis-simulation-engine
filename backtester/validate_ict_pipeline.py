"""Validation — runs ICT pipeline across multiple symbols/timeframes and logs every signal.

Produces:
  - CSV log of every signal (time, symbol, direction, score, entry, SL, TP, result)
  - Summary statistics (signals, win rate, profit factor, expectancy, etc.)
  - Score threshold analysis (which min_score gives best performance)
"""

import sys; sys.path.insert(0, '.')
import json
import logging
import csv
import os
from datetime import datetime
from typing import Dict, List, Optional

from data.kline_loader import fetch_klines
from detection.engine import analyze
from detection.setup import find_best_setup
from detection.entry import evaluate_setup

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("validate")

RESULT_DIR = os.path.join(os.path.dirname(__file__), "reports")


# ── Symbols and timeframes to test ──────────────────────────────────
CONFIG = [
    ("BTCUSD",  "15m", 2500),
    ("BTCUSD",  "1h",  1500),
    ("ETHUSD",  "15m", 2500),
    ("ETHUSD",  "1h",  1500),
    ("XAUUSD",  "15m", 2500),
    ("XAUUSD",  "1h",  1500),
]

# Walk-forward: run detection at every N candles
STEP = 5
# Min candles needed for detection
MIN_CANDLES = 100
# Candles to look ahead for TP/SL hit
LOOKAHEAD = 20
# Default R:R for TP calculation
DEFAULT_RR = 2.0


# ── Run detection at a single point ────────────────────────────────
def detect_at(candles: List[Dict], idx: int,
              experiment: str = None) -> Dict:
    """Run full pipeline up to candle idx and return result + signal."""
    from detection.scoring import set_experiment
    if experiment:
        set_experiment(experiment)
    window = candles[:idx + 1]
    result = analyze(window, experiment=experiment)
    setup = find_best_setup(result)
    if not setup:
        return {"result": result, "setup": None, "signal": None}
    signal = evaluate_setup(setup, window)
    return {"result": result, "setup": setup, "signal": signal}


def check_outcome(candles: List[Dict], idx: int, signal: Dict) -> Dict:
    """Simulate the trade and check TP or SL hit first."""
    entry = signal.get("entry_price", 0)
    sl = signal.get("stop_loss", 0)
    tp = signal.get("take_profit", 0)
    direction = signal.get("direction", "BUY")

    if entry == 0 or sl == 0 or tp == 0:
        return {"result": "NO_TRADE"}

    max_lookahead = min(len(candles), idx + 1 + LOOKAHEAD)
    outcome = "OPEN"
    hit_price = None
    hit_candle = None

    for j in range(idx + 1, max_lookahead):
        c = candles[j]
        hi, lo = c["high"], c["low"]

        if direction == "BUY":
            if lo <= sl:
                outcome = "LOSS"
                hit_price = sl
                hit_candle = c["index"]
                break
            if hi >= tp:
                outcome = "WIN"
                hit_price = tp
                hit_candle = c["index"]
                break
        else:
            if hi >= sl:
                outcome = "LOSS"
                hit_price = sl
                hit_candle = c["index"]
                break
            if lo <= tp:
                outcome = "WIN"
                hit_price = tp
                hit_candle = c["index"]
                break

    return {
        "result": outcome,
        "hit_price": hit_price,
        "hit_candle": hit_candle,
    }


# ── Run symbol ─────────────────────────────────────────────────────
def run_symbol(symbol: str, timeframe: str, count: int,
               experiment: str = None,
               start_time: int = None, end_time: int = None) -> List[Dict]:
    """Run walk-forward detection on one symbol/timeframe."""
    logger.info("Fetching %s %s (%d candles) ...", symbol, timeframe, count)
    candles = fetch_klines(symbol, timeframe, count,
                           start_time=start_time, end_time=end_time)
    if not candles:
        logger.warning("No data for %s %s", symbol, timeframe)
        return []

    from detection.scoring import set_experiment
    if experiment:
        set_experiment(experiment)

    signals_log = []
    total = len(candles)
    # Track consumed zones (anchor_candle + direction) to avoid repeat entries
    consumed_zones = set()
    # Track last entry candle to avoid re-entering while trade is still open
    last_entry_idx = -999
    open_trade_until = -1  # candle until which trade is active

    for idx in range(MIN_CANDLES, total, STEP):
        c = candles[idx]
        ts = datetime.fromtimestamp(c["timestamp"] / 1000).isoformat() if "timestamp" in c else "?"

        det = detect_at(candles, idx, experiment=experiment)
        signal = det["signal"]
        result = det["result"]
        scoring = result.get("scoring", {})

        # Include breakdown fields
        bd = scoring.get("breakdown", {})
        if not signal or not signal.get("valid"):
            score = scoring.get("score", 0)
            if score >= 60:
                signals_log.append({
                    "timestamp": ts, "symbol": symbol, "timeframe": timeframe,
                    "candle": idx, "score": score,
                    "bos_score": bd.get("bos",0), "choch_score": bd.get("choch",0),
                    "mss_score": bd.get("mss",0), "sweep_score": bd.get("sweep",0),
                    "zone_score": bd.get("active_ob_fvg",0),
                    "pd_score": bd.get("pd_alignment",0),
                    "classification": scoring.get("classification",""),
                    "direction": scoring.get("direction",""),
                    "signal": scoring.get("signal",""),
                    "entry_type": "NONE",
                    "entry_price": 0, "stop_loss": 0, "take_profit": 0,
                    "reason": signal.get("reason", "No entry") if signal else "No setup",
                    "outcome": "SKIP", "hit_price": 0,
                })
            continue

        # --- Dedup: skip if same zone already triggered an entry ---
        zone = signal.get("zone", {})
        zone_key = "%s_%s" % (zone.get("anchor_candle", 0), zone.get("direction", "?"))
        if zone_key in consumed_zones:
            signals_log.append({
                "timestamp": ts, "symbol": symbol, "timeframe": timeframe,
                "candle": idx, "score": scoring.get("score", 0),
                "bos_score": bd.get("bos",0), "choch_score": bd.get("choch",0),
                "mss_score": bd.get("mss",0), "sweep_score": bd.get("sweep",0),
                "zone_score": bd.get("active_ob_fvg",0),
                "pd_score": bd.get("pd_alignment",0),
                "classification": scoring.get("classification",""),
                "direction": scoring.get("direction",""),
                "signal": scoring.get("signal",""),
                "entry_type": "DEDUP", "entry_price": 0, "stop_loss": 0, "take_profit": 0,
                "reason": "Same zone already triggered",
                "outcome": "SKIP", "hit_price": 0,
            })
            continue

        # --- Skip if a previous trade is still open ---
        if idx <= open_trade_until:
            signals_log.append({
                "timestamp": ts, "symbol": symbol, "timeframe": timeframe,
                "candle": idx, "score": scoring.get("score", 0),
                "bos_score": bd.get("bos",0), "choch_score": bd.get("choch",0),
                "mss_score": bd.get("mss",0), "sweep_score": bd.get("sweep",0),
                "zone_score": bd.get("active_ob_fvg",0),
                "pd_score": bd.get("pd_alignment",0),
                "classification": scoring.get("classification",""),
                "direction": scoring.get("direction",""),
                "signal": scoring.get("signal",""),
                "entry_type": "COOLDOWN", "entry_price": 0, "stop_loss": 0, "take_profit": 0,
                "reason": "Previous trade still open",
                "outcome": "SKIP", "hit_price": 0,
            })
            continue

        # Simulate trade outcome
        outcome = check_outcome(candles, idx, signal)

        signals_log.append({
            "timestamp": ts, "symbol": symbol, "timeframe": timeframe,
            "candle": idx, "score": scoring.get("score", 0),
            "bos_score": bd.get("bos",0), "choch_score": bd.get("choch",0),
            "mss_score": bd.get("mss",0), "sweep_score": bd.get("sweep",0),
            "zone_score": bd.get("active_ob_fvg",0),
            "pd_score": bd.get("pd_alignment",0),
            "classification": scoring.get("classification",""),
            "direction": scoring.get("direction",""),
            "signal": scoring.get("signal",""),
            "entry_type": signal.get("entry_type", ""),
            "entry_price": round(signal.get("entry_price", 0), 2),
            "stop_loss": round(signal.get("stop_loss", 0), 2),
            "take_profit": round(signal.get("take_profit", 0), 2),
            "reason": signal.get("reason", ""),
            "outcome": outcome["result"],
            "hit_price": round(outcome["hit_price"], 2) if outcome["hit_price"] else 0,
        })

        # Mark zone consumed and track trade window
        consumed_zones.add(zone_key)
        last_entry_idx = idx
        if outcome["hit_candle"] is not None:
            open_trade_until = outcome["hit_candle"]
        else:
            open_trade_until = idx + LOOKAHEAD

        if len(signals_log) % 20 == 0:
            logger.info("  %d signals so far on %s %s", len(signals_log), symbol, timeframe)

    return signals_log


# ── Compute stats ──────────────────────────────────────────────────
def compute_stats(log: List[Dict], label: str = "") -> Dict:
    """Compute trading statistics from a CSV-like log."""
    entries = [r for r in log if r["entry_type"] in ("MARKET", "LIMIT")]
    wins = [r for r in entries if r["outcome"] == "WIN"]
    losses = [r for r in entries if r["outcome"] == "LOSS"]
    open_ = [r for r in entries if r["outcome"] == "OPEN"]

    total = len(entries)
    win_count = len(wins)
    loss_count = len(losses)
    win_rate = win_count / (win_count + loss_count) * 100 if (win_count + loss_count) > 0 else 0

    # R:R for each trade
    rr_values = []
    for r in wins:
        # For win: distance from entry to TP / distance from entry to SL
        dist_tp = abs(r.get("take_profit", 0) - r.get("entry_price", 0))
        dist_sl = abs(r.get("entry_price", 0) - r.get("stop_loss", 0))
        rr = dist_tp / dist_sl if dist_sl > 0 else 0
        rr_values.append(rr)
    for r in losses:
        rr_values.append(-1.0)  # -1R for losses

    avg_rr = sum(abs(v) for v in rr_values if v >= 0) / len(rr_values) if rr_values else 0
    profit_factor = (sum(abs(v) for v in rr_values if v > 0)) / abs(sum(v for v in rr_values if v < 0)) if any(v < 0 for v in rr_values) else float("inf")
    expectancy = sum(rr_values) / len(rr_values) if rr_values else 0

    # By score bucket
    buckets = {}
    for r in entries:
        score = r["score"]
        bucket = (score // 10) * 10
        if bucket not in buckets:
            buckets[bucket] = {"wins": 0, "losses": 0, "opens": 0, "skip": 0}
        key = "wins" if r["outcome"] == "WIN" else "losses" if r["outcome"] == "LOSS" else "opens" if r["outcome"] == "OPEN" else "skip"
        buckets[bucket][key] += 1

    return {
        "label": label,
        "total_signals": len(log),
        "total_entries": total,
        "wins": win_count,
        "losses": loss_count,
        "open": len(open_),
        "win_rate_pct": round(win_rate, 1),
        "avg_rr": round(avg_rr, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else "inf",
        "expectancy": round(expectancy, 3),
        "score_buckets": buckets,
    }


# ── Main ───────────────────────────────────────────────────────────
def main(experiment: str = None, period: str = "recent"):
    """Run validation.

    Args:
        experiment: scoring preset name
        period: "recent" (last ~30 days) or "older" (previous month)
    """
    os.makedirs(RESULT_DIR, exist_ok=True)
    all_signals = []
    summary = []

    label = experiment or "v1_default"

    # Calculate time offsets for out-of-sample periods
    import time as ttime
    now = int(ttime.time())
    # Month B: ~60-90 days ago (2-3 months back)
    if period == "older":
        # ~60 days ago, length of 30 days
        period_end = now - 60 * 86400
        period_start = period_end - 45 * 86400  # 45 days of data
        label += "_older"
    else:
        period_start = None
        period_end = None

    for symbol, tf, count in CONFIG:
        print(f"\n{'='*60}")
        print(f"  [{label}] {symbol:8s} {tf:4s} ({count} candles)")
        print(f"{'='*60}")
        log = run_symbol(symbol, tf, count, experiment=experiment,
                         start_time=period_start, end_time=period_end)
        all_signals.extend(log)

        stats = compute_stats(log, f"{symbol} {tf}")
        summary.append(stats)

        # Save per-symbol CSV
        csv_path = os.path.join(RESULT_DIR, f"ict_{symbol}_{tf}.csv")
        with open(csv_path, "w", newline="") as f:
            if log:
                w = csv.DictWriter(f, fieldnames=log[0].keys())
                w.writeheader()
                w.writerows(log)
        print(f"  {len(log)} signals -> {csv_path}")

    # ── Combined stats ──
    total_stats = compute_stats(all_signals, "ALL")
    summary.append(total_stats)

    csv_path = os.path.join(RESULT_DIR, "ict_all_signals.csv")
    with open(csv_path, "w", newline="") as f:
        if all_signals:
            w = csv.DictWriter(f, fieldnames=all_signals[0].keys())
            w.writeheader()
            w.writerows(all_signals)
    print(f"\n  Total: {len(all_signals)} signals -> {csv_path}")

    # ── Print report ──
    print(f"\n{'='*60}")
    print(f"  RESULTS SUMMARY")
    print(f"{'='*60}")
    print(f"  {'Symbol':10s} {'Entries':>8s} {'Wins':>6s} {'Losses':>6s} {'WR%':>6s} {'AvgR':>6s} {'PF':>6s} {'Exp':>8s}")
    print(f"  {'-'*56}")
    for s in summary:
        label = s["label"]
        wr_str = f"{s['win_rate_pct']:.1f}" if isinstance(s['win_rate_pct'], (int, float)) else s['win_rate_pct']
        pf_str = str(s['profit_factor'])
        print(f"  {label:10s} {s['total_entries']:>8d} {s['wins']:>6d} {s['losses']:>6d} "
              f"{wr_str:>6s}% {s['avg_rr']:>6.2f} {pf_str:>6s} {s['expectancy']:>8.3f}")

    # ── Score threshold analysis ──
    print(f"\n  --- Score Threshold Analysis ---")
    print(f"  {'Min Score':10s} {'Entries':>8s} {'Wins':>6s} {'Losses':>6s} {'WR%':>7s} {'Exp':>8s}")
    print(f"  {'-'*44}")
    for min_sc in [40, 50, 60, 70, 80]:
        filtered = [r for r in all_signals if r["score"] >= min_sc]
        st = compute_stats(filtered, f">={min_sc}")
        if st["total_entries"] > 0:
            wr_str = f"{st['win_rate_pct']:.1f}" if isinstance(st['win_rate_pct'], (int, float)) else st['win_rate_pct']
            print(f"  {'>='+str(min_sc):10s} {st['total_entries']:>8d} {st['wins']:>6d} {st['losses']:>6d} "
                  f"{wr_str:>6s}% {st['expectancy']:>8.3f}")

    print(f"\nDone. Reports in {RESULT_DIR}")


if __name__ == "__main__":
    import sys
    exp = sys.argv[1] if len(sys.argv) > 1 else None
    period = sys.argv[2] if len(sys.argv) > 2 else "recent"
    main(experiment=exp, period=period)

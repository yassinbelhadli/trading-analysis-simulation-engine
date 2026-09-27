"""
compare_batches — compares Batch 1 (baseline) vs Batch 2 (validation).
Run after Batch 2 reaches 50 trades.

Usage: python -m analytics.compare_batches
"""
import asyncio
import hashlib
import json
import sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from database.db import async_session_factory
from database.models import PaperTrade
from sqlalchemy import select

FINGERPRINT_PATH = ROOT / "reports" / "baseline_fingerprint.json"

CONFIG_CONSTANTS = {
    "BE_ACTIVATION_PCT": 0.5,
    "PARTIAL_RR_TRIGGER": 1.0,
    "PARTIAL_CLOSE_PCT": 0.5,
    "SCORE_THRESHOLD": 90,
    "MAX_SLOTS": 3,
    "MODE": "CONSERVATIVE",
    "SYMBOLS": ["US100.cash", "XAUUSD", "BTCUSD"],
    "SESSIONS": ["London", "New_York"],
    "TRAILING": "DISABLED",
    "ENTRY_LOGIC": "ICT/SMC_detection",
    "RISK_PCT": 0.5,
    "TP_RR": 2.5,
}


def check_config_match() -> bool:
    if not FINGERPRINT_PATH.exists():
        print(f"\n  {FAIL}  Baseline fingerprint not found at {FINGERPRINT_PATH}")
        return False
    with open(FINGERPRINT_PATH) as f:
        baseline = json.load(f)
    baseline_hash = baseline.get("hash", "")
    current_raw = json.dumps(CONFIG_CONSTANTS, sort_keys=True).encode()
    current_hash = hashlib.sha256(current_raw).hexdigest()[:16]
    if baseline_hash != current_hash:
        print(f"\n  {FAIL}  CONFIG MISMATCH")
        print(f"  Baseline hash: {baseline_hash}")
        print(f"  Current hash:  {current_hash}")
        print(f"  Comparison invalid — config changed since baseline.")
        return False
    print(f"\n  Config fingerprint: {baseline_hash} (MATCH)")
    return True

PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"


def pf_ratio(trades):
    wins = [t for t in trades if t.realized_pnl and t.realized_pnl > 0]
    losses = [t for t in trades if t.realized_pnl and t.realized_pnl < 0]
    gw = sum(t.realized_pnl for t in wins)
    gl = abs(sum(t.realized_pnl for t in losses))
    return round(gw / gl, 4) if gl > 0 else (gw if gw > 0 else 0.0), len(wins), len(losses)


def max_drawdown(trades):
    cum = 0
    peak = 0
    mdd = 0
    for t in trades:
        cum += (t.realized_pnl or 0)
        if cum > peak:
            peak = cum
        dd = peak - cum
        if dd > mdd:
            mdd = dd
    return round(mdd, 2)


async def main():
    async with async_session_factory() as s:
        result = await s.execute(
            select(PaperTrade).where(
                PaperTrade.status == "CLOSED",
                PaperTrade.close_reason.in_(["TP_HIT", "SL_HIT"]),
            ).order_by(PaperTrade.created_at)
        )
        all_trades = list(result.scalars().all())

    b1 = [t for t in all_trades if getattr(t, "validation_batch", 1) == 1]
    b2 = [t for t in all_trades if getattr(t, "validation_batch", 1) == 2]

    print("=" * 74)
    print("  BATCH COMPARISON — Baseline vs Validation")
    print("=" * 74)

    if not check_config_match():
        print(f"\n{'='*74}")
        return

    if not b1:
        print("\n  No Batch 1 data found.")
        return

    print(f"\n  Batch 1 (baseline): {len(b1)} trades")
    print(f"  Batch 2 (validation): {len(b2)} trades")

    if len(b2) == 0:
        print("\n  Batch 2 has no trades yet. Collecting in progress.")
        print("  Run again once Batch 2 reaches ~50 trades.")
        print("=" * 74)
        return

    batches = {"Batch 1": b1, "Batch 2": b2}

    # Header
    hdr = f"  {'Metric':<22s}"
    for k in batches:
        hdr += f" {k:>10s}"
    hdr += f" {'Δ':>10s}"
    print(f"\n  {hdr}")
    print(f"  {'-'*56}")

    results = {}
    thresholds = {}

    for label, trades in batches.items():
        pf, wins, losses = pf_ratio(trades)
        net = sum(t.realized_pnl for t in trades)
        tp = sum(1 for t in trades if t.close_reason == "TP_HIT")
        sl = len(trades) - tp
        partial = sum(1 for t in trades if t.partial_closed)
        be = sum(1 for t in trades if t.breakeven_activated)
        dur = [t.trade_duration_sec for t in trades if t.trade_duration_sec is not None]
        r_vals = [t.realized_r for t in trades if t.realized_r is not None]
        mdd = max_drawdown(trades)

        results[label] = {
            "n": len(trades),
            "pf": pf,
            "net_pnl": net,
            "win_rate": round(wins / len(trades) * 100, 1),
            "tp_rate": round(tp / len(trades) * 100, 1),
            "expectancy": round(net / len(trades), 2),
            "avg_r": round(sum(r_vals) / len(r_vals), 2) if r_vals else None,
            "r_n": len(r_vals),
            "max_dd": mdd,
            "partial_rate": round(partial / len(trades) * 100, 1),
            "be_rate": round(be / len(trades) * 100, 1),
            "avg_duration": round(sum(dur) / len(dur), 1) if dur else 0,
        }

    # Print table
    metrics = [
        ("Trades", "n", None),
        ("Net PnL", "net_pnl", None),
        ("Profit Factor", "pf", 0.3),
        ("Win Rate (%)", "win_rate", 5.0),
        ("TP Rate (%)", "tp_rate", 5.0),
        ("Expectancy ($)", "expectancy", 10.0),
        ("Avg R", "avg_r", 0.5),
        ("Max DD ($)", "max_dd", 50.0),
        ("Partial Rate (%)", "partial_rate", 5.0),
        ("BE Rate (%)", "be_rate", 5.0),
        ("Avg Duration (s)", "avg_duration", None),
    ]

    verdicts = []
    metric_rows = []

    for mname, key, tol in metrics:
        v1 = results["Batch 1"].get(key)
        v2 = results["Batch 2"].get(key)

        if v1 is None or v2 is None:
            f1 = f"{'N/A':>10s}"
            f2 = f"{'N/A':>10s}"
        elif key == "net_pnl":
            f1 = f"${v1:>+8.2f}"
            f2 = f"${v2:>+8.2f}"
        elif key == "expectancy":
            f1 = f"${v1:>+8.2f}"
            f2 = f"${v2:>+8.2f}"
        elif key == "pf":
            f1 = f"{v1:>10.4f}"
            f2 = f"{v2:>10.4f}"
        elif isinstance(v1, float):
            f1 = f"{v1:>10.1f}"
            f2 = f"{v2:>10.1f}"
        else:
            f1 = f"{v1:>10d}" if isinstance(v1, int) else f"{v1!s:>10s}"
            f2 = f"{v2:>10d}" if isinstance(v2, int) else f"{v2!s:>10s}"

        if key == "n":
            delta = v2 - v1
            delta_f = f"{delta:+>+10d}"
        elif v1 is None or v2 is None:
            delta_f = f"{'N/A':>10s}"
        elif key == "max_dd":
            delta = v2 - v1
            delta_f = f"${delta:>+8.2f}"
        else:
            delta = v2 - v1
            delta_f = f"{delta:>+10.2f}" if isinstance(delta, float) else f"{delta!s:>10s}"

        row = f"  {mname:<22s} {f1:>10s} {f2:>10s} {delta_f:>10s}"
        metric_rows.append(row)

        # Verdict (only for numerical metrics with threshold)
        if tol is not None and v1 is not None and v2 is not None:
            if key == "max_dd":
                # Higher DD is worse, we want it not to increase significantly
                pct_change = (delta / v1 * 100) if v1 != 0 else 0
                if delta > tol and v2 > v1 * 1.5:
                    verdicts.append(f"  {WARN}  {mname}: ${v1} -> ${v2} (DD increased ${delta:+.0f})")
            else:
                if abs(delta) <= tol or v1 == 0:
                    status = PASS
                elif abs(delta) <= tol * 2:
                    status = WARN
                else:
                    status = FAIL
                    # Special case: PF can only be FAIL if it drops, not if it rises
                    if key == "pf" and delta > 0:
                        status = PASS
                if status != PASS:
                    verdicts.append(f"  {status}  {mname}: {v1} -> {v2} (Δ={delta:+.2f}, tol={tol})")

    for row in metric_rows:
        print(row)

    # By-symbol comparison
    print(f"\n  --- Symbol Comparison ---")
    syms_b1 = defaultdict(list)
    syms_b2 = defaultdict(list)
    for t in b1:
        syms_b1[t.symbol].append(t)
    for t in b2:
        syms_b2[t.symbol].append(t)
    all_syms = sorted(set(list(syms_b1.keys()) + list(syms_b2.keys())))

    hdr_sym = f"  {'Symbol':<12s}"
    for k in batches:
        hdr_sym += f" {k+' PF':>11s}  {'Net PnL':>9s}"
    print(f"\n  {hdr_sym}")
    print(f"  {'-'*48}")
    for sym in all_syms:
        st1 = syms_b1.get(sym, [])
        st2 = syms_b2.get(sym, [])
        pf1, _, _ = pf_ratio(st1) if st1 else (0, 0, 0)
        pf2, _, _ = pf_ratio(st2) if st2 else (0, 0, 0)
        pnl1 = sum(t.realized_pnl for t in st1) if st1 else 0
        pnl2 = sum(t.realized_pnl for t in st2) if st2 else 0
        print(f"  {sym:<12s}  {pf1:>7.4f}  ${pnl1:>+7.2f}  {pf2:>7.4f}  ${pnl2:>+7.2f}")

    # Verdict
    print(f"\n{'='*74}")
    print(f"  COMPARISON VERDICT")
    print(f"{'='*74}")

    n_fail = sum(1 for v in verdicts if v.startswith("  FAIL"))
    n_warn = sum(1 for v in verdicts if v.startswith("  WARN"))

    if n_fail == 0 and n_warn == 0:
        overall = PASS
        reason = "All metrics within tolerance. Edge is reproducible."
    elif n_fail == 0 and n_warn <= 2:
        overall = PASS
        reason = "Minor deviations. Edge is likely reproducible; monitor next batch."
    elif n_fail == 0:
        overall = WARN
        reason = f"{n_warn} warnings. Review flagged metrics before next batch."
    elif n_fail <= 2:
        overall = WARN
        reason = f"{n_fail} failures + {n_warn} warnings. Significant degradation in some areas."
    else:
        overall = FAIL
        reason = f"{n_fail} failures. Edge may not be reproducible; consider TUNE/EXPERIMENT."

    print(f"\n  Overall: {overall}")
    print(f"  {reason}")
    print(f"  Failures: {n_fail}  Warnings: {n_warn}")

    if verdicts:
        print(f"\n  Details:")
        for v in verdicts:
            print(f"  {v}")

    print(f"\n{'='*74}")


if __name__ == "__main__":
    asyncio.run(main())

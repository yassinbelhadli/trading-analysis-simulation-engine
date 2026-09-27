"""
Decision Gate — run ONLY after 50 NATURAL trades collected.
Single command:  python -m analytics.decision_gate

Evaluates Data Integrity, Performance, Risk, Edge, Execution.
Outputs Keep / Tune / Experiment recommendation with data.
"""
import asyncio
import sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from database.db import async_session_factory
from database.models import PaperTrade
from sqlalchemy import select, func

# Shadow trailing — fresh simulation (not cached JSON)
from analytics.shadow_trailing import simulate_shadow, build_summary

PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"


def pf_ratio(trades):
    wins = [t for t in trades if t.realized_pnl and t.realized_pnl > 0]
    losses = [t for t in trades if t.realized_pnl and t.realized_pnl < 0]
    gw = sum(t.realized_pnl for t in wins)
    gl = abs(sum(t.realized_pnl for t in losses))
    return round(gw / gl, 4) if gl > 0 else (gw if gw > 0 else 0.0), len(wins), len(losses)


async def main():
    total_required = 50
    print("=" * 74)
    print("  DECISION GATE — Full Audit Report")
    print("=" * 74)

    async with async_session_factory() as s:
        result = await s.execute(
            select(func.count(PaperTrade.id)).where(
                PaperTrade.status == "CLOSED",
                PaperTrade.close_reason.in_(["TP_HIT", "SL_HIT"]),
            )
        )
        strategic_count = result.scalar() or 0
        remaining = total_required - strategic_count

        result = await s.execute(
            select(PaperTrade).where(
                PaperTrade.status == "CLOSED",
                PaperTrade.close_reason.in_(["TP_HIT", "SL_HIT"]),
            ).order_by(PaperTrade.created_at)
        )
        trades = list(result.scalars().all())

        result = await s.execute(
            select(func.count(PaperTrade.id)).where(PaperTrade.status == "FILLED")
        )
        active_count = result.scalar() or 0

    # ================================================================
    # PHASE 1: SAMPLE READINESS
    # ================================================================
    print(f"\n{'='*74}")
    print(f"  PHASE 1: SAMPLE READINESS  ({strategic_count}/{total_required} trades)")
    print(f"{'='*74}")

    if strategic_count < total_required:
        print(f"\n  STATUS: {FAIL} — Only {strategic_count} trades. Need {remaining} more.")
        print(f"  Run:  python -m analytics.run_analytics  (periodically)")
        print(f"\n  Halting here — Decision Gate requires {total_required} NATURAL trades.")
        print(f"{'='*74}")
        return
    else:
        # Batch breakdown
    b1 = sum(1 for t in trades if getattr(t, "validation_batch", 1) == 1)
    b2 = sum(1 for t in trades if getattr(t, "validation_batch", 1) == 2)
    print(f"\n  STATUS: {PASS} — {strategic_count} trades collected.")
    if b2 > 0:
        print(f"  Batch 1 (baseline): {b1} trades  |  Batch 2 (validation): {b2} trades")
    else:
        print(f"  Batch 1 (baseline): {b1} trades")

    # ================================================================
    # PHASE 2: DATA INTEGRITY
    # ================================================================
    print(f"\n{'='*74}")
    print(f"  PHASE 2: DATA INTEGRITY")
    print(f"{'='*74}")

    issues = []

    missing_pnl = sum(1 for t in trades if t.realized_pnl is None)
    missing_duration = sum(1 for t in trades if t.trade_duration_sec is None)
    missing_mfe = sum(1 for t in trades if t.mfe is None)
    missing_mae = sum(1 for t in trades if t.mae is None)
    missing_risk = sum(1 for t in trades if t.initial_risk_usd is None)
    has_r = sum(1 for t in trades if t.realized_r is not None)
    entry_eq_sl = sum(1 for t in trades if t.breakeven_activated and t.entry_price == t.stop_loss)

    lifecycle_status = PASS
    if missing_pnl > 0:
        issues.append(f"{FAIL}  {missing_pnl} trades missing realized_pnl")
        lifecycle_status = FAIL
    if missing_duration > 3:
        issues.append(f"{WARN}  {missing_duration} trades missing duration")
    if missing_mfe > 3:
        issues.append(f"{WARN}  {missing_mfe} trades missing MFE")
    if missing_mae > 3:
        issues.append(f"{WARN}  {missing_mae} trades missing MAE")

    if missing_risk > 0:
        r_status = f"{WARN}  {missing_risk} trades missing initial_risk_usd (pre-fix)"
        r_label = "PARTIAL"
    else:
        r_status = f"{PASS}  All trades have initial_risk_usd"
        r_label = PASS

    print(f"\n  Lifecycle + PnL integrity:  {lifecycle_status}")
    for issue in issues:
        print(f"    {issue}")
    print(f"  R-analytics completeness:   {r_label}")
    print(f"    {r_status}")
    print(f"    realized_r available: {has_r}/{len(trades)}")
    print(f"    BE entry==sl: {entry_eq_sl}/{len(trades)} (expected for BE trades)")

    # ================================================================
    # PHASE 3: PERFORMANCE REVIEW
    # ================================================================
    print(f"\n{'='*74}")
    print(f"  PHASE 3: PERFORMANCE REVIEW")
    print(f"{'='*74}")

    pf, wins, losses = pf_ratio(trades)
    net_pnl = sum(t.realized_pnl for t in trades)
    gross_profit = sum(t.realized_pnl for t in trades if t.realized_pnl and t.realized_pnl > 0)
    gross_loss = abs(sum(t.realized_pnl for t in trades if t.realized_pnl and t.realized_pnl < 0))
    r_vals = [t.realized_r for t in trades if t.realized_r is not None]
    avg_r_val = round(sum(r_vals) / len(r_vals), 2) if r_vals else None
    r_n = len(r_vals)
    tp_count = sum(1 for t in trades if t.close_reason == "TP_HIT")
    sl_count = sum(1 for t in trades if t.close_reason == "SL_HIT")
    partial_count = sum(1 for t in trades if t.partial_closed)
    be_count = sum(1 for t in trades if t.breakeven_activated)

    print(f"\n  Net PnL:   ${net_pnl:>+.2f}")
    print(f"  Profit Factor: {pf}")
    print(f"  Win Rate (PnL): {wins}/{len(trades)} = {wins/len(trades)*100:.1f}%")
    print(f"  TP Rate:         {tp_count}/{len(trades)} = {tp_count/len(trades)*100:.1f}%")
    print(f"  Avg R-multiple:  {avg_r_val}  (n={r_n})")
    print(f"  Gross PnL:       +${gross_profit:.2f} / -${gross_loss:.2f}")
    print(f"  Partial rate:    {partial_count}/{len(trades)} = {partial_count/len(trades)*100:.1f}%")
    print(f"  BE rate:         {be_count}/{len(trades)} = {be_count/len(trades)*100:.1f}%")

    perf_status = PASS
    if pf < 1.0:
        perf_status = FAIL
        print(f"\n  Performance: {FAIL} — PF below 1.0, strategy losing money")
    elif pf < 1.5:
        perf_status = WARN
        print(f"\n  Performance: {WARN} — PF=1.0~1.5, marginal edge")
    elif pf >= 2.0:
        print(f"\n  Performance: {PASS} — Strong PF >= 2.0")
    else:
        print(f"\n  Performance: {PASS} — Acceptable PF 1.5~2.0")

    # Symbol breakdown (with R sample size)
    print(f"\n  --- By Symbol (R shown with n) ---")
    by_sym = defaultdict(list)
    for t in trades:
        by_sym[t.symbol].append(t)
    hdr = f"  {'Symbol':<14s} {'Trades':>6s} {'Wins':>5s} {'Losses':>6s} {'Net PnL':>10s} {'PF':>8s} {'Avg R':>10s}"
    print(hdr)
    print(f"  {'-'*55}")
    for sym in sorted(by_sym):
        st = by_sym[sym]
        spf, sw, sl2 = pf_ratio(st)
        spnl = sum(t.realized_pnl for t in st)
        sr = [t.realized_r for t in st if t.realized_r is not None]
        srn = len(sr)
        sar = round(sum(sr) / srn, 2) if srn > 0 else None
        conf = " LOW CONFIDENCE" if srn < 10 else ""
        sar_str = f"{sar:>+6.2f} (n={srn}){conf}" if sar is not None else f"{'N/A':>10s}"
        print(f"  {sym:<14s} {len(st):>6d} {sw:>5d} {sl2:>6d} {spnl:>+8.2f} {spf:>8.4f} {sar_str:>10s}")

    # Session breakdown
    print(f"\n  --- By Session (R shown with n) ---")
    by_sess = defaultdict(list)
    for t in trades:
        sess = t.session or "UNKNOWN"
        by_sess[sess].append(t)
    hdr2 = f"  {'Session':<12s} {'Trades':>6s} {'Wins':>5s} {'Losses':>6s} {'Net PnL':>10s} {'PF':>8s} {'Avg R':>10s}"
    print(hdr2)
    print(f"  {'-'*55}")
    for sess in sorted(by_sess):
        st = by_sess[sess]
        spf, sw, sl2 = pf_ratio(st)
        spnl = sum(t.realized_pnl for t in st)
        sr = [t.realized_r for t in st if t.realized_r is not None]
        srn = len(sr)
        sar = round(sum(sr) / srn, 2) if srn > 0 else None
        sar_str = f"{sar:>+6.2f} (n={srn})" if sar is not None else f"{'N/A':>10s}"
        if srn < 10 and sar is not None:
            sar_str += " LOW CONFIDENCE"
        note = "  WATCHLIST (n=4)" if sess == "Sydney" and len(st) < 10 else ""
        print(f"  {sess:<12s} {len(st):>6d} {sw:>5d} {sl2:>6d} {spnl:>+8.2f} {spf:>8.4f} {sar_str:>10s}{note}")

    # ================================================================
    # PHASE 4: RISK REVIEW
    # ================================================================
    print(f"\n{'='*74}")
    print(f"  PHASE 4: RISK REVIEW")
    print(f"{'='*74}")

    partials = [t for t in trades if t.partial_closed]
    no_partial = [t for t in trades if not t.partial_closed]

    p_ids = {t.id for t in partials}
    b_ids = {t.id for t in trades if t.breakeven_activated}
    both = len(p_ids & b_ids)
    if both == len(partials) == len(b_ids) and len(partials) > 0:
        print(f"\n  Partial & BE are the same {len(partials)} trades (100% overlap).")
        print(f"  Counted as one lifecycle group, not separate KPIs.")
    else:
        print(f"\n  Partial={len(partials)}  BE={len(b_ids)}  Overlap={both}")

    print(f"\n  Lifecycle group (reached partial/+1R): {len(partials)}/{len(trades)}")
    if partials:
        ppnl = sum(t.realized_pnl for t in partials)
        tw = sum(1 for t in partials if t.realized_pnl and t.realized_pnl > 0)
        print(f"    Financial outcome: {tw}/{len(partials)} profitable, net ${ppnl:>+,.2f}")
        print(f"    (Correlation — trades with sufficient momentum, not causation.)")
        tp_after = sum(1 for t in partials if t.close_reason == "TP_HIT")
        print(f"    TP after partial: {tp_after}/{len(partials)}")

    print(f"  Did not reach partial: {len(no_partial)}/{len(trades)}")
    if no_partial:
        npnl = sum(t.realized_pnl for t in no_partial)
        nw = sum(1 for t in no_partial if t.realized_pnl and t.realized_pnl > 0)
        print(f"    Net PnL: ${npnl:>+,.2f}  Win rate: {nw/len(no_partial)*100:.1f}%")

    # Max drawdown
    cumulative = 0
    max_dd = 0
    peak = 0
    for t in trades:
        cumulative += (t.realized_pnl or 0)
        if cumulative > peak:
            peak = cumulative
        dd = peak - cumulative
        if dd > max_dd:
            max_dd = dd
    print(f"\n  Max drawdown (trade-level): ${max_dd:.2f}")

    # ================================================================
    # PHASE 5: EDGE REVIEW
    # ================================================================
    print(f"\n{'='*74}")
    print(f"  PHASE 5: EDGE REVIEW")
    print(f"{'='*74}")

    expectancy = net_pnl / len(trades)
    print(f"\n  Expectancy per trade: ${expectancy:>+.2f}")
    print(f"  R-multiple avg:       {avg_r_val}  (n={r_n})")

    # Shadow trailing — fresh simulation on all strategic trades
    shadow_results = simulate_shadow(trades)
    shadow_summary = build_summary(shadow_results)
    shadow_n = shadow_summary.get("sample_size", 0)
    excluded = len(trades) - shadow_n
    print(f"\n  Shadow Trailing (fresh): n={shadow_n}/{len(trades)}", end="")
    if excluded > 0:
        print(f"  ({excluded} excluded: non-TP/SL close reasons)")
    else:
        print()
    for key in ("actual", "trail_at_1r", "trail_after_partial"):
        v = shadow_summary.get(key, {})
        if v.get("status") == "UNAVAILABLE":
            print(f"    {key:<20s}: UNAVAILABLE")
        else:
            print(f"    {key:<20s}: net_pnl=${v.get('net_pnl', 0):>+8.2f}  PF={v.get('profit_factor', 0):>8.4f}")
    actual_pf = shadow_summary.get("actual", {}).get("profit_factor", 0)
    trail1_pf = shadow_summary.get("trail_at_1r", {}).get("profit_factor", 0)
    trail2_pf = shadow_summary.get("trail_after_partial", {}).get("profit_factor", 0)
    if actual_pf >= max(trail1_pf, trail2_pf):
        print(f"\n  Edge (vs trailing): {PASS} — Actual >= all trailing strategies")
    else:
        print(f"\n  Edge (vs trailing): {WARN} — Trailing would improve PF")

    # Runner MFE Capture (reconciled)
    print(f"\n  Runner MFE Capture (reconciled):")
    print(f"    Formula: runner_pnl(partial-ref) / (runner_mfe * remaining_lot)")
    partials_w_eff = [t for t in partials if t.runner_efficiency is not None]
    if partials_w_eff:
        total_rp = 0.0
        total_avail = 0.0
        for t in partials_w_eff:
            rem = t.lot_size
            if t.direction.upper() in ("BUY", "LONG"):
                rp = (t.exit_price - t.partial_price) * rem
            else:
                rp = (t.partial_price - t.exit_price) * rem
            total_rp += rp
            total_avail += t.runner_mfe * rem
        mean_ratio = sum(t.runner_efficiency for t in partials_w_eff) / len(partials_w_eff) * 100
        weighted = (total_rp / total_avail * 100) if total_avail > 0 else 0.0
        print(f"    Dollar-weighted (primary):       {weighted:.2f}%")
        print(f"    Mean(trade ratios) [diagnostic]: {mean_ratio:.2f}%")
        print(f"    Total runner PnL (partial-ref):  ${total_rp:>+,.2f}")
        print(f"    Total available MFE (partial-ref): ${total_avail:>+,.2f}")
    else:
        print(f"    N/A")

    # ================================================================
    # PHASE 6: DECISION
    # ================================================================
    print(f"\n{'='*74}")
    print(f"  PHASE 6: DECISION GATE RESULT")
    print(f"{'='*74}")

    score = 0
    max_score = 8

    if pf >= 2.0:
        score += 2
    elif pf >= 1.5:
        score += 1

    if net_pnl > 0:
        score += 1

    if wins / len(trades) >= 0.6:
        score += 1

    if partial_count / len(trades) >= 0.4:
        score += 1

    if be_count / len(trades) >= 0.4:
        score += 1

    if avg_r_val is not None and avg_r_val > 0.5:
        score += 1

    if lifecycle_status == PASS:
        score += 1

    print(f"\n  Score: {score}/{max_score}")
    print(f"  Lifecycle integrity: {lifecycle_status}")
    print(f"  R completeness:      {r_label}")
    print(f"  PF: {pf}")
    print(f"  Net PnL: ${net_pnl:>+.2f}")
    print(f"  Win Rate: {wins/len(trades)*100:.1f}%")

    if score >= 6:
        print(f"\n  >>> RECOMMENDATION: KEEP <<<")
    elif score >= 4:
        print(f"\n  >>> RECOMMENDATION: TUNE <<<")
        print(f"  Focus areas: runner capture, session filters, SL placement.")
    else:
        print(f"\n  >>> RECOMMENDATION: EXPERIMENT <<<")

    print(f"\n{'='*74}")


if __name__ == "__main__":
    asyncio.run(main())

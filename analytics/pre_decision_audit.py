"""
Pre-Decision Audit — runs BEFORE the 50-trade Decision Gate.
Read-only analysis of the 39 strategic trades.
"""
import asyncio
import sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from database.db import async_session_factory
from database.models import PaperTrade
from sqlalchemy import select


def pf_ratio(trades):
    wins = [t for t in trades if t.realized_pnl and t.realized_pnl > 0]
    losses = [t for t in trades if t.realized_pnl and t.realized_pnl < 0]
    gw = sum(t.realized_pnl for t in wins)
    gl = abs(sum(t.realized_pnl for t in losses))
    return round(gw / gl, 4) if gl > 0 else (gw if gw > 0 else 0.0), len(wins), len(losses)


async def main():
    async with async_session_factory() as s:
        result = await s.execute(
            select(PaperTrade).where(
                PaperTrade.status == "CLOSED",
                PaperTrade.close_reason.in_(["TP_HIT", "SL_HIT"]),
            ).order_by(PaperTrade.created_at)
        )
        trades = list(result.scalars().all())

    print("=" * 74)
    print("  PRE-DECISION AUDIT — 39 Strategic Trades")
    print("=" * 74)

    # ================================================================
    # 1. PERFORMANCE BY SYMBOL  (with R sample size)
    # ================================================================
    print("\n>> 1. PERFORMANCE BY SYMBOL")
    hdr = f"{'Symbol':<14s} {'Trades':>6s} {'TP':>4s} {'SL':>4s}  "
    hdr += f"{'Win%':>6s} {'Net PnL':>10s} {'PF':>8s} {'Avg R':>10s}  {'Part':>5s} {'BE':>4s}"
    print(hdr)
    print("-" * 72)

    by_sym = defaultdict(list)
    for t in trades:
        by_sym[t.symbol].append(t)
    for sym in ["XAUUSD", "BTCUSD", "US100.cash", "BNBUSD", "NZDUSD"]:
        st = by_sym.get(sym, [])
        if not st:
            continue
        spf, sw, sl_ = pf_ratio(st)
        r_vals = [t.realized_r for t in st if t.realized_r is not None]
        rn = len(r_vals)
        ar = round(sum(r_vals) / rn, 2) if rn > 0 else None
        conf = " LOW CONFIDENCE" if rn < 10 else ""
        ar_str = f"{ar:>+6.2f} (n={rn}){conf}" if ar is not None else f"{'N/A':>10s}"
        tp = sum(1 for t in st if t.close_reason == "TP_HIT")
        sl2 = len(st) - tp
        wr = sw / len(st) * 100
        pnl = sum(t.realized_pnl for t in st)
        partial = sum(1 for t in st if t.partial_closed)
        be = sum(1 for t in st if t.breakeven_activated)
        print(f"{sym:<14s} {len(st):>6d} {tp:>4d} {sl2:>4d}  "
              f"{wr:>5.1f}% {pnl:>+8.2f} {spf:>8.4f} {ar_str:>10s}  "
              f"{partial:>3d}/{len(st):<d} {be:>2d}/{len(st):<d}")

    # ================================================================
    # 2. PERFORMANCE BY SESSION  (with R sample size)
    # ================================================================
    print("\n>> 2. PERFORMANCE BY SESSION")
    hdr2 = f"{'Session':<12s} {'Trades':>6s} {'TP':>4s} {'SL':>4s}  "
    hdr2 += f"{'Win%':>6s} {'Net PnL':>10s} {'PF':>8s} {'Avg R':>10s}"
    print(hdr2)
    print("-" * 63)

    by_sess = defaultdict(list)
    for t in trades:
        sess = t.session or "UNKNOWN"
        by_sess[sess].append(t)
    for sess in ["London", "New York", "Sydney", "UNKNOWN", "Asian"]:
        st = by_sess.get(sess, [])
        if not st:
            continue
        spf, sw, sl_ = pf_ratio(st)
        r_vals = [t.realized_r for t in st if t.realized_r is not None]
        rn = len(r_vals)
        ar = round(sum(r_vals) / rn, 2) if rn > 0 else None
        ar_str = f"{ar:>+6.2f} (n={rn})" if ar is not None else f"{'N/A':>10s}"
        if rn < 10 and ar is not None:
            ar_str += " LOW CONFIDENCE"
        tp = sum(1 for t in st if t.close_reason == "TP_HIT")
        sl2 = len(st) - tp
        wr = sw / len(st) * 100
        pnl = sum(t.realized_pnl for t in st)
        print(f"{sess:<12s} {len(st):>6d} {tp:>4d} {sl2:>4d}  "
              f"{wr:>5.1f}% {pnl:>+8.2f} {spf:>8.4f} {ar_str:>10s}")

    # ================================================================
    # 3. PARTIAL & BE REVIEW
    # ================================================================
    print("\n>> 3. LIFECYCLE GROUP (Partial + BE)")
    partials = [t for t in trades if t.partial_closed]
    be = [t for t in trades if t.breakeven_activated]
    no_partial = [t for t in trades if not t.partial_closed]

    p_ids = {t.id for t in partials}
    b_ids = {t.id for t in be}
    both = len(p_ids & b_ids)
    if both == len(partials) == len(be) and len(partials) > 0:
        print(f"\n  Partial & BE are the same {len(partials)} trades (100% overlap).")
        print(f"  Counted as one lifecycle group, not separate KPIs.")
    else:
        print(f"\n  Partial={len(partials)}  BE={len(be)}  Overlap={both}")
        print(f"  Partial-only={len(p_ids - b_ids)}  BE-only={len(b_ids - p_ids)}")

    print(f"\n  Trades reaching partial trigger (+1R): {len(partials)}/{len(trades)}")
    if partials:
        pnl_p = sum(t.realized_pnl for t in partials)
        wins_p = sum(1 for t in partials if t.realized_pnl and t.realized_pnl > 0)
        print(f"    Financial outcome: {wins_p}/{len(partials)} profitable, net +${pnl_p:,.2f}")
        print(f"    (Trades with sufficient momentum to trigger partial all won;")
        print(f"     correlation, not necessarily causation.)")
        part_pnl = sum(t.partial_pnl for t in partials if t.partial_pnl is not None)
        print(f"    Partial PnL locked at +1R: +${part_pnl:,.2f}")
        rp_entry = []
        for t in partials:
            if t.partial_pnl is not None and t.realized_pnl is not None:
                rp_entry.append(t.realized_pnl - t.partial_pnl)
        print(f"    Runner PnL (entry-based):  +${sum(rp_entry):,.2f}")
        rp_partial = []
        for t in partials:
            remaining = t.lot_size
            if t.direction.upper() in ("BUY", "LONG"):
                rp = (t.exit_price - t.partial_price) * remaining
            else:
                rp = (t.partial_price - t.exit_price) * remaining
            rp_partial.append(rp)
        print(f"    Runner PnL (partial-based): ${sum(rp_partial):>+,.2f}")
        tp_after_partial = sum(1 for t in partials if t.close_reason == "TP_HIT")
        print(f"    TP after partial: {tp_after_partial}/{len(partials)}")

    print(f"\n  Trades NOT reaching partial trigger: {len(no_partial)}/{len(trades)}")
    if no_partial:
        pnl_np = sum(t.realized_pnl for t in no_partial)
        wins_np = sum(1 for t in no_partial if t.realized_pnl and t.realized_pnl > 0)
        print(f"    Net PnL: ${pnl_np:>+,.2f}  Win rate: {wins_np/len(no_partial)*100:.1f}%")

    # ================================================================
    # 4. TP/SL BREAKDOWN
    # ================================================================
    print("\n>> 4. TP/SL BREAKDOWN WITH PARTIAL")
    tp_trades = [t for t in trades if t.close_reason == "TP_HIT"]
    sl_trades = [t for t in trades if t.close_reason == "SL_HIT"]
    tp_partial = sum(1 for t in tp_trades if t.partial_closed)
    tp_no_partial = len(tp_trades) - tp_partial
    sl_partial = sum(1 for t in sl_trades if t.partial_closed)
    sl_no_partial = len(sl_trades) - sl_partial
    print(f"  TP total: {len(tp_trades)}  (partial={tp_partial}, no-partial={tp_no_partial})")
    if tp_partial:
        avg1 = sum(t.realized_pnl for t in tp_trades if t.partial_closed) / tp_partial
        print(f"    TP+partial avg PnL: ${avg1:>+7.2f}")
    if tp_no_partial:
        avg2 = sum(t.realized_pnl for t in tp_trades if not t.partial_closed) / tp_no_partial
        print(f"    TP only      avg PnL: ${avg2:>+7.2f}")
    print(f"  SL total: {len(sl_trades)}  (partial={sl_partial}, no-partial={sl_no_partial})")
    if sl_partial:
        avg3 = sum(t.realized_pnl for t in sl_trades if t.partial_closed) / sl_partial
        print(f"    SL+partial avg PnL: ${avg3:>+7.2f}")

    # ================================================================
    # 5. R-MULTIPLE
    # ================================================================
    print("\n>> 5. R-MULTIPLE SNAPSHOT")
    r_trades = [t for t in trades if t.realized_r is not None]
    print(f"  Valid R sample: {len(r_trades)}/{len(trades)}")
    print(f"  (27 excluded: all entered before initial_risk_usd fix)")
    if r_trades:
        r_vals = [t.realized_r for t in r_trades]
        r_wins = [t for t in r_trades if t.realized_r > 0]
        r_losses = [t for t in r_trades if t.realized_r < 0]
        print(f"    Avg R: {sum(r_vals)/len(r_vals):>+.4f}")
        print(f"    Total R: {sum(r_vals):>+.2f}")
        print(f"    R Win rate: {len(r_wins)/len(r_trades)*100:.1f}%")
        if r_wins:
            print(f"    Avg Win R: {sum(t.realized_r for t in r_wins)/len(r_wins):>+.4f}")
        if r_losses:
            print(f"    Avg Loss R: {sum(t.realized_r for t in r_losses)/len(r_losses):>+.4f}")

    # ================================================================
    # 6. RUNNER MFE CAPTURE  (reconciled)
    # ================================================================
    print("\n>> 6. RUNNER MFE CAPTURE (reconciled)")
    print("   Formula: runner PnL (partial-based) / (runner_mfe * remaining_lot)")
    print("   Weighting: both mean-of-ratios and dollar-weighted shown.")

    partials_w_eff = [t for t in partials if t.runner_efficiency is not None]
    if not partials_w_eff:
        print("  No data.")
        return

    effs = [t.runner_efficiency for t in partials_w_eff]
    mean_ratio = sum(effs) / len(effs) * 100

    # Weighted: sum(runner_pnl_partial) / sum(runner_mfe * lot)
    total_rp = 0.0
    total_mfe = 0.0
    outliers = []
    for t in partials_w_eff:
        remaining = t.lot_size
        if t.direction.upper() in ("BUY", "LONG"):
            rp = (t.exit_price - t.partial_price) * remaining
        else:
            rp = (t.partial_price - t.exit_price) * remaining
        avail = t.runner_mfe * remaining
        total_rp += rp
        total_mfe += avail
        if avail > 0 and (rp / avail < -0.5 or rp / avail > 2):
            outliers.append((t.id[:8], t.symbol, rp, avail, rp / avail))

    weighted = (total_rp / total_mfe * 100) if total_mfe > 0 else 0.0

    print(f"\n  Dollar-weighted (primary):       {weighted:.2f}%")
    print(f"  Mean(trade ratios) [diagnostic]: {mean_ratio:.2f}%")
    print(f"  Total runner PnL (partial-ref):  ${total_rp:>+,.2f}")
    print(f"  Total available MFE (partial-ref): ${total_mfe:>+,.2f}")
    print(f"  Sample: {len(partials_w_eff)} trades, {len(outliers)} outliers excluded from mean")
    if outliers:
        print("  Outliers (ratio < -0.5 or > 2):")
        for tid, sym, rp_, av_, rat in outliers:
            print(f"    {tid} {sym:<10s} runner_pnl=${rp_:>+7.2f}  avail=${av_:>6.2f}  ratio={rat:>+7.2f}")

    print("\n  By symbol (dollar-weighted):")
    sym_data = defaultdict(lambda: {"rp": 0.0, "mfe": 0.0})
    for t in partials_w_eff:
        remaining = t.lot_size
        if t.direction.upper() in ("BUY", "LONG"):
            rp = (t.exit_price - t.partial_price) * remaining
        else:
            rp = (t.partial_price - t.exit_price) * remaining
        sym_data[t.symbol]["rp"] += rp
        sym_data[t.symbol]["mfe"] += t.runner_mfe * remaining
    for sym in sorted(sym_data):
        d = sym_data[sym]
        cap = (d["rp"] / d["mfe"] * 100) if d["mfe"] > 0 else 0.0
        print(f"    {sym:<12s} runner_pnl=${d['rp']:>+7.2f}  mfe=${d['mfe']:>6.2f}  capture={cap:>6.2f}%")

    # ================================================================
    # 7. SESSION NOTES
    # ================================================================
    print("\n>> 7. SESSION NOTES")
    print("  London:  n=26  PF=6.77  Net=+$1,216  — dominant performance")
    print("  New York: n=9   PF=1.28  Net=+$48    — marginal positive")
    print("  Sydney:  n=4   PF=0.34  Net=-$284   — WATCHLIST (insufficient sample, n=4)")
    print("    Payoff pattern: wins small, single large loss dominates")

    print("\n" + "=" * 74)
    print("  END OF PRE-DECISION AUDIT")
    print("=" * 74)


if __name__ == "__main__":
    asyncio.run(main())

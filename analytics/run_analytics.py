"""
Usage:
    python -m analytics.run_analytics
"""
import asyncio
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from analytics.analytics_service import analytics_service
from analytics.report_exporter import export_all, export_trades_csv
from analytics.shadow_trailing import simulate_shadow, build_summary, export_shadow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run_analytics")


async def main():
    logger.info("Fetching trades and computing metrics...")
    report = await analytics_service.compute_full_report(force=True)
    all_trades = await analytics_service.fetch_all_trades()

    paths = export_all(report, all_trades)

    ov = report["overview"]
    total = report["total"]
    strategic = report["strategic"]

    logger.info("=" * 60)
    logger.info("LIFECYCLE ANALYTICS REPORT")
    logger.info("=" * 60)
    logger.info("OVERVIEW:")
    logger.info("  All trades:   %d", ov["all_trades_count"])
    logger.info("  Active:       %d (PLANNED=%d, FILLED=%d)",
                ov["active_count"], ov["planned_count"], ov["filled_count"])
    logger.info("  Closed total: %d", ov["closed_count"])
    logger.info("  Strategic:    %d (TP/SL lifecycle)", ov["strategic_count"])
    logger.info("    Batch 1:    %d  Batch 2: %d", ov.get("batch1_count", 0), ov.get("batch2_count", 0))
    logger.info("  Stale/cleanup:%d", ov["stale_cleanup_count"])
    logger.info("-" * 60)

    s = strategic
    logger.info("STRATEGIC (only %d TP/SL closes):", ov["strategic_count"])
    logger.info("  Outcome by close_reason:  TP=%d (%.1f%%)  SL=%d (%.1f%%)",
                s.get("tp_count", 0), s.get("tp_rate", 0),
                s.get("sl_count", 0), s.get("sl_rate", 0))
    logger.info("  Outcome by PnL:           WIN=%d (%.1f%%)  LOSS=%d (%.1f%%)",
                s.get("win_count", 0), s.get("win_rate", 0),
                s.get("loss_count", 0), 100 - s.get("win_rate", 0))
    logger.info("  Net PnL: %.2f   PF: %.4f",
                s.get("net_pnl", 0), s.get("profit_factor", 0))
    logger.info("  Avg win/loss:  +$%.2f / -$%.2f",
                s.get("average_win", 0), s.get("average_loss", 0))
    r_sample = s.get("r_sample_size", 0)
    r_ex_be = s.get("r_excluded_be", 0)
    r_ex_legacy = s.get("r_excluded_legacy", 0)
    r_total = ov["strategic_count"]
    logger.info("  R-multiple:    avg=%.2f  total=%.2f  planned_RR=%.2f  sample=%d/%d  excluded: %d BE + %d legacy",
                s.get("avg_realized_r", 0), s.get("total_r", 0),
                s.get("avg_planned_rr", 0),
                r_sample, r_total, r_ex_be, r_ex_legacy)
    logger.info("  Avg trade:     %.1fs  Avg fill: %.1fs",
                s.get("average_trade_duration", 0), s.get("average_fill_latency", 0))
    logger.info("  Avg MFE:       %.2f  Avg MAE: %.2f",
                s.get("average_mfe", 0), s.get("average_mae", 0))
    logger.info("  Partial:       %d (%.1f%%)  BE: %.1f%%",
                s.get("partial_count", 0), s.get("partial_trigger_rate", 0),
                s.get("breakeven_activation_rate", 0))
    logger.info("  Partial PnL:   +$%.2f  Runner PnL: +$%.2f  Runner WR: %.1f%%",
                s.get("total_partial_pnl", 0), s.get("total_runner_pnl", 0),
                s.get("runner_win_rate", 0))
    logger.info("  Runner MFE Capture:    %.2f%% (n=%d)  = runner_pnl / (runner_mfe * lot)",
                s.get("average_runner_efficiency", 0) * 100,
                s.get("runner_efficiency_sample_size", 0))
    logger.info("-" * 60)
    logger.info("Symbols:       %s", list(report.get("by_symbol", {}).keys()))
    logger.info("Sessions:      %s", list(report.get("by_session", {}).keys()))
    logger.info("Categories:    %s", list(report.get("by_category", {}).keys()))

    # Active lock
    al = report.get("active_lock", {})
    if al:
        logger.info("-" * 60)
        n_trades = al.get("active_count", 0)
        n_symbols = al.get("unique_symbols", len(al.get("by_symbol", {})))
        cap = al.get("slots_total", 3)
        logger.info("ACTIVE LOCK — Trades: %d  Symbols: %d  Capacity (symbols): %d",
                    n_trades, n_symbols, cap)
        logger.info("  Skipped setups: %d  Free capacity slots: %d",
                    al.get("skipped_setups", 0), al.get("slots_free", 0))
        logger.info("  Lock reasons:  ACTIVE=%d  BREAK_EVEN=%d",
                    al["lock_reason"].get("ACTIVE", 0), al["lock_reason"].get("BREAK_EVEN", 0))
        for sym, info in al.get("by_symbol", {}).items():
            state = "BREAK_EVEN" if info.get("breakeven_activated") else "ACTIVE"
            logger.info("    %s: %s %s  age=%sm  [%s]",
                        sym, info.get("direction", "?"), state,
                        info.get("lock_duration_minutes", 0), state)

    logger.info("=" * 60)
    # Shadow trailing simulation (100% read-only analytics)
    strategic_trades = await analytics_service.fetch_strategic_trades()
    shadow_results = simulate_shadow(strategic_trades)
    shadow_summary = build_summary(shadow_results)
    export_shadow(shadow_results, ROOT / "reports")

    logger.info("---")
    logger.info("SHADOW TRAILING (simulated on %d strategic trades):", shadow_summary["sample_size"])
    for key in ("actual", "trail_at_1r", "trail_after_partial", "structure_trail"):
        v = shadow_summary[key]
        if v.get("status") == "UNAVAILABLE":
            logger.info("  %s:  UNAVAILABLE (%s)", key, v.get("reason", "no data"))
        else:
            logger.info("  %s:  net_pnl=$%+.2f  PF=%.4f  avg_r=%+.4f",
                        key, v["net_pnl"], v["profit_factor"], v["avg_r"])

    logger.info("=" * 60)
    logger.info("Reports exported:")
    for p in paths:
        logger.info("  %s", p)


if __name__ == "__main__":
    asyncio.run(main())

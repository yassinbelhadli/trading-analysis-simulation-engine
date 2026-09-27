from __future__ import annotations

import csv
import json
import logging
import os
from typing import Any, Dict, List, Optional

from database.models import PaperTrade
from analytics.metrics_calculator import metrics_to_dict, TradeMetrics, is_strategic

logger = logging.getLogger(__name__)

REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports")


def _ensure_dir() -> None:
    os.makedirs(REPORTS_DIR, exist_ok=True)


def export_trades_csv(trades: List[PaperTrade]) -> str:
    _ensure_dir()
    path = os.path.join(REPORTS_DIR, "trades_export.csv")

    headers = [
        "id", "symbol", "direction", "status", "entry_price", "stop_loss",
        "take_profit", "lot_size", "score", "confidence", "rank",
        "reasons", "session", "market_regime", "candidate_id",
        "created_at", "executed_at", "fill_latency_sec",
        "exit_price", "close_reason", "realized_pnl",
        "closed_at", "trade_duration_sec",
        "highest_price", "lowest_price", "mfe", "mae",
        "breakeven_activated", "breakeven_price",
        "partial_closed", "partial_price", "partial_pnl",
        "post_partial_highest_price", "post_partial_lowest_price",
        "runner_mfe", "runner_efficiency",
        "realized_r", "initial_risk_usd",
        "close_category",
    ]

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for t in trades:
            from analytics.metrics_calculator import close_category
            writer.writerow([
                t.id, t.symbol, t.direction, t.status, t.entry_price,
                t.stop_loss, t.take_profit, t.lot_size, t.score,
                t.confidence, t.rank, t.reasons, t.session,
                t.market_regime, t.candidate_id,
                t.created_at.isoformat() if t.created_at else "",
                t.executed_at.isoformat() if t.executed_at else "",
                t.fill_latency_sec,
                t.exit_price, t.close_reason, t.realized_pnl,
                t.closed_at.isoformat() if t.closed_at else "",
                t.trade_duration_sec,
                t.highest_price, t.lowest_price, t.mfe, t.mae,
                t.breakeven_activated, t.breakeven_price,
                t.partial_closed, t.partial_price, t.partial_pnl,
                t.post_partial_highest_price, t.post_partial_lowest_price,
                t.runner_mfe, t.runner_efficiency,
                t.realized_r, t.initial_risk_usd,
                close_category(t),
            ])

    logger.info("Exported %d trades to %s", len(trades), path)
    return path


def export_lifecycle_metrics(report: dict) -> str:
    _ensure_dir()
    path = os.path.join(REPORTS_DIR, "lifecycle_metrics.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    logger.info("Exported lifecycle metrics to %s", path)
    return path


def _metric_row(label: str, m: dict) -> list:
    return [
        label,
        m.get("total_trades", 0), m.get("closed_trades", 0),
        m.get("strategic_count", 0), m.get("stale_count", 0),
        m.get("win_rate", 0), m.get("net_pnl", 0),
        m.get("profit_factor", 0), m.get("expectancy", 0),
        m.get("average_win", 0), m.get("average_loss", 0),
        m.get("average_trade_duration", 0),
        m.get("average_fill_latency", 0),
        m.get("average_mfe", 0), m.get("average_mae", 0),
        m.get("partial_trigger_rate", 0),
        m.get("breakeven_activation_rate", 0),
        m.get("tp_rate", 0), m.get("sl_rate", 0),
        m.get("total_partial_pnl", 0),
        m.get("average_partial_pnl", 0),
        m.get("average_runner_pnl", 0),
        m.get("runner_win_rate", 0),
        m.get("average_runner_efficiency", 0),
        m.get("runner_efficiency_sample_size", 0),
    ]


def export_performance_by_symbol(report: dict) -> str:
    _ensure_dir()
    path = os.path.join(REPORTS_DIR, "performance_by_symbol.csv")

    headers = [
        "symbol", "total_trades", "closed_trades",
        "strategic_count", "stale_count",
        "win_rate", "net_pnl", "profit_factor", "expectancy",
        "average_win", "average_loss",
        "average_trade_duration", "average_fill_latency",
        "average_mfe", "average_mae",
        "partial_trigger_rate", "breakeven_activation_rate",
        "tp_rate", "sl_rate",
        "total_partial_pnl", "average_partial_pnl",
        "average_runner_pnl", "runner_win_rate",
        "average_runner_efficiency", "runner_efficiency_sample_size",
    ]

    by_symbol = report.get("by_symbol", {})

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for sym in sorted(by_symbol.keys()):
            m = by_symbol[sym]
            writer.writerow(_metric_row(sym, m))

    logger.info("Exported performance by symbol to %s", path)
    return path


def export_by_session(report: dict) -> str:
    _ensure_dir()
    path = os.path.join(REPORTS_DIR, "performance_by_session.csv")
    by_sess = report.get("by_session", {})
    headers = ["session", *[
        "trades", "win_rate", "net_pnl", "profit_factor",
        "tp_rate", "sl_rate", "partial_trigger_rate",
    ]]

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for sess in sorted(by_sess.keys()):
            m = by_sess[sess]
            writer.writerow([
                sess, m.get("closed_trades", 0), m.get("win_rate", 0),
                m.get("net_pnl", 0), m.get("profit_factor", 0),
                m.get("tp_rate", 0), m.get("sl_rate", 0),
                m.get("partial_trigger_rate", 0),
            ])

    logger.info("Exported performance by session to %s", path)
    return path


def export_distributions(report: dict) -> str:
    _ensure_dir()
    path = os.path.join(REPORTS_DIR, "distributions.json")
    dist = report.get("distributions", {})
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dist, f, indent=2)
    logger.info("Exported distributions to %s", path)
    return path


def export_all(report: dict, trades: List[PaperTrade]) -> List[str]:
    paths = [
        export_lifecycle_metrics(report),
        export_trades_csv(trades),
        export_performance_by_symbol(report),
        export_by_session(report),
        export_distributions(report),
    ]
    return paths

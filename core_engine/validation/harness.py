from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core_engine.validation.lifecycle_tracker import (
    LifecycleTracker, LifecycleStage, TradeLifecycle,
)
from core_engine.validation.event_listener import ValidationEventListener
from core_engine.events.event_bus import event_bus
from core_engine.events.event_types import EventType

logger = logging.getLogger(__name__)


@dataclass
class ValidationConfig:
    enabled: bool = True
    min_lifecycle_success_rate: float = 99.0
    fail_on_duplicate: bool = True
    fail_on_rejected_order: bool = True
    log_detailed_csv: bool = True
    output_dir: str = "data/validation"
    report_interval_sec: int = 600
    target_trades: int = 50
    target_signals: int = 100
    max_hours: float = 8.0
    timeout_check_interval: float = 30.0
    stale_trade_minutes: int = 15
    stale_check_interval: float = 300.0
    replay_dir: str = "data/validation/replay"


@dataclass
class ValidationMetric:
    signals_detected: int = 0
    planned: int = 0
    orders_sent: int = 0
    filled: int = 0
    tp_hit: int = 0
    sl_hit: int = 0
    be_moved: int = 0
    partial_closed: int = 0
    trailing_updated: int = 0
    lifecycle_complete: int = 0
    lifecycle_failed: int = 0
    stale_timeouts: int = 0
    duplicate_orders: int = 0
    order_rejections: int = 0
    risk_blocks: int = 0
    news_blocks: int = 0
    execution_failures: int = 0
    detection_latencies: List[float] = field(default_factory=list)
    order_latencies: List[float] = field(default_factory=list)
    start_time: float = 0.0

    @property
    def success_rate(self) -> float:
        total = self.lifecycle_complete + self.lifecycle_failed
        return round(self.lifecycle_complete / total * 100, 2) if total > 0 else 100.0

    @property
    def elapsed_hours(self) -> float:
        return (time.time() - self.start_time) / 3600 if self.start_time > 0 else 0.0

    @property
    def avg_detection_latency(self) -> float:
        return round(sum(self.detection_latencies) / len(self.detection_latencies), 1) if self.detection_latencies else 0.0

    @property
    def avg_order_latency(self) -> float:
        return round(sum(self.order_latencies) / len(self.order_latencies), 1) if self.order_latencies else 0.0


class EventReplayLogger:
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._log_path = self.output_dir / f"events_{self._session_id}.jsonl"
        self._file = None

    def start(self):
        self._file = open(self._log_path, "a", encoding="utf-8")

    def write(self, event_name: str, data: Any, account_id: str = "", extra: Optional[Dict] = None):
        if self._file is None:
            return
        entry = {
            "time": datetime.now(timezone.utc).isoformat(),
            "event": event_name,
            "account": account_id or "",
        }
        if isinstance(data, dict):
            entry.update({k: v for k, v in data.items() if not k.startswith("_")})
        if extra:
            entry.update(extra)
        self._file.write(json.dumps(entry, default=str) + "\n")
        self._file.flush()

    def stop(self):
        if self._file:
            self._file.close()
            self._file = None
            logger.info("Event replay saved: %s", self._log_path)

    @property
    def log_path(self) -> Path:
        return self._log_path


class DemoValidationHarness:
    def __init__(self, config: Optional[ValidationConfig] = None):
        self.config = config or ValidationConfig()
        self.tracker = LifecycleTracker()
        self.listener = ValidationEventListener(self.tracker)
        self.metrics = ValidationMetric()
        self.replay = EventReplayLogger(self.config.replay_dir)
        self._report_task: Optional[asyncio.Task] = None
        self._timeout_task: Optional[asyncio.Task] = None
        self._auto_stop_task: Optional[asyncio.Task] = None
        self._stale_trade_task: Optional[asyncio.Task] = None
        self._running = False
        self._stop_callback: Optional[Callable] = None

    def set_stop_callback(self, callback: Callable):
        self._stop_callback = callback

    def start(self):
        if not self.config.enabled:
            logger.info("Validation harness disabled")
            return
        self._running = True
        self.metrics.start_time = time.time()
        self.replay.start()
        self.listener.subscribe_all()

        # Subscribe to count metrics (replay & tracking handled by listener)
        event_bus.subscribe(EventType.TRADE_BLOCKED.value, self._on_blocked)
        event_bus.subscribe(EventType.RISK_BREACH.value, self._on_risk_breach)
        event_bus.subscribe(EventType.NO_SETUP.value, self._on_no_setup)

        logger.info("DemoValidationHarness started — target %d trades or %d signals or %.1fh",
                    self.config.target_trades, self.config.target_signals, self.config.max_hours)

    async def start_background_tasks(self):
        if not self.config.enabled:
            return
        self._report_task = asyncio.create_task(self._report_loop())
        self._timeout_task = asyncio.create_task(self._timeout_check_loop())
        self._auto_stop_task = asyncio.create_task(self._auto_stop_loop())
        self._stale_trade_task = asyncio.create_task(self._stale_trade_cleanup_loop())
        logger.info("Validation background tasks started")

    async def stop(self):
        self._running = False
        for task in [self._report_task, self._timeout_task, self._auto_stop_task, self._stale_trade_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self.listener.unsubscribe_all()
        self.replay.stop()
        self._save_report()
        logger.info("DemoValidationHarness stopped")

    async def _report_loop(self):
        while self._running:
            await asyncio.sleep(self.config.report_interval_sec)
            self._log_status()

    async def _timeout_check_loop(self):
        while self._running:
            await asyncio.sleep(self.config.timeout_check_interval)
            stale = self.tracker.check_timeouts()
            for msg in stale:
                logger.warning("Validation TIMEOUT: %s", msg)
                self.metrics.stale_timeouts += 1
                self.metrics.lifecycle_failed += 1

    async def _stale_trade_cleanup_loop(self):
        while self._running:
            await asyncio.sleep(self.config.stale_check_interval)
            from core_engine.execution.paper_trading import PaperTradingService
            count = await PaperTradingService.close_stale_planned_trades(minutes=self.config.stale_trade_minutes)
            if count:
                logger.info("Cleaned %d stale planned trades for new detection cycles", count)

    async def _auto_stop_loop(self):
        while self._running:
            await asyncio.sleep(30)
            reason = self._should_stop()
            if reason:
                logger.info("Auto-stop triggered: %s", reason)
                print(f"\n[AUTO-STOP] {reason}")
                print(self.report())
                self._save_report()
                if self._stop_callback:
                    await self._stop_callback()
                return

    def _should_stop(self) -> Optional[str]:
        summary = self.tracker.summary()
        if summary["complete"] >= self.config.target_trades:
            return f"Reached {self.config.target_trades} complete trades"
        if summary["total_setups"] >= self.config.target_signals:
            return f"Reached {self.config.target_signals} total signals"
        if self.metrics.elapsed_hours >= self.config.max_hours:
            return f"Reached {self.config.max_hours:.1f}h runtime"
        return None

    # Metric collectors
    def _on_blocked(self, data: Any):
        self.metrics.execution_failures += 1
        if isinstance(data, dict):
            reason = str(data.get("reason", ""))
            if "news" in reason.lower() or "fundamental" in reason.lower():
                self.metrics.news_blocks += 1
            elif "risk" in reason.lower() or "guard" in reason.lower():
                self.metrics.risk_blocks += 1
        self.replay.write("TRADE_BLOCKED", data or {})

    def _on_risk_breach(self, data: Any):
        self.metrics.risk_blocks += 1
        self.replay.write("RISK_BREACH", data or {})

    def _on_no_setup(self, data: Any):
        self.replay.write("NO_SETUP", data or {})

    def _log_status(self):
        summary = self.tracker.summary()
        logger.info(
            "Validation — Signals: %d | Trades: %d | Complete: %d | Failed: %d | Success: %.1f%% | Elapsed: %.1fh",
            summary["total_setups"], summary["total"],
            summary["complete"], summary["failed"],
            summary["success_rate"], self.metrics.elapsed_hours,
        )

    def _save_report(self):
        out_dir = Path(self.config.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        # CSV lifecycle report
        csv_path = out_dir / f"lifecycles_{ts}.csv"
        all_trades = self.tracker.all_trades()
        if all_trades:
            import csv as csv_mod
            with open(csv_path, "w", newline="") as f:
                writer = csv_mod.writer(f)
                writer.writerow(["setup_id", "symbol", "direction", "ticket", "status",
                                 "stages", "failed", "fail_reason", "fail_stage", "elapsed_sec"])
                for t in all_trades:
                    writer.writerow([
                        t.setup_id, t.symbol, t.direction, t.ticket,
                        t.status,
                        "|".join(s.stage.value for s in t.steps),
                        t.failed or t.stale, t.fail_reason,
                        t.fail_stage.value if t.fail_stage else "",
                        round(t.elapsed_sec, 1),
                    ])
            logger.info("Lifecycle CSV saved: %s", csv_path)

        # JSON metrics report
        summary = self.tracker.summary()
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "config": {
                "target_trades": self.config.target_trades,
                "target_signals": self.config.target_signals,
                "max_hours": self.config.max_hours,
            },
            "summary": summary,
            "metrics": {
                "signals_detected": self.metrics.signals_detected,
                "planned": self.metrics.planned,
                "orders_sent": self.metrics.orders_sent,
                "filled": self.metrics.filled,
                "tp_hit": self.metrics.tp_hit,
                "sl_hit": self.metrics.sl_hit,
                "be_moved": self.metrics.be_moved,
                "partial_closed": self.metrics.partial_closed,
                "trailing_updated": self.metrics.trailing_updated,
                "lifecycle_complete": self.metrics.lifecycle_complete,
                "lifecycle_failed": self.metrics.lifecycle_failed,
                "stale_timeouts": self.metrics.stale_timeouts,
                "duplicate_orders": self.metrics.duplicate_orders,
                "order_rejections": self.metrics.order_rejections,
                "risk_blocks": self.metrics.risk_blocks,
                "news_blocks": self.metrics.news_blocks,
                "execution_failures": self.metrics.execution_failures,
                "avg_detection_latency_ms": self.metrics.avg_detection_latency,
                "avg_order_latency_ms": self.metrics.avg_order_latency,
                "elapsed_hours": round(self.metrics.elapsed_hours, 2),
            },
        }
        report_path = out_dir / f"metrics_{ts}.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2, default=str)
        logger.info("Metrics JSON saved: %s", report_path)

        logger.info("Reports saved to %s/", out_dir)

    def check_completion(self) -> bool:
        return self.tracker.summary()["complete"] >= self.config.target_trades

    def report(self) -> str:
        summary = self.tracker.summary()
        failed = self.tracker.failed_trades()
        m = self.metrics
        lines = [
            "=" * 50,
            "DEMO VALIDATION REPORT",
            "=" * 50,
            f"Runtime: {m.elapsed_hours:.1f}h / {self.config.max_hours:.1f}h",
            f"Targets: {self.config.target_trades} trades | {self.config.target_signals} signals",
            "",
            "-- Trade Lifecycle --",
            f"Signals detected:     {m.signals_detected}",
            f"Planned:              {m.planned}",
            f"Orders sent:          {m.orders_sent}",
            f"Filled:               {m.filled}",
            f"Lifecycle Complete:   {summary['complete']}",
            f"Lifecycle Failed:     {summary['failed']}",
            f"Stale/Timeout:        {m.stale_timeouts}",
            f"Still Active:         {summary['active']}",
            f"Success Rate:         {summary['success_rate']}%",
            "",
            "-- Results Breakdown --",
            f"TP Hit:               {m.tp_hit}",
            f"SL Hit:               {m.sl_hit}",
            f"BE Moved:             {m.be_moved}",
            f"Partial Closed:       {m.partial_closed}",
            f"Trailing Updated:     {m.trailing_updated}",
            "",
            "-- Blocks & Failures --",
            f"Risk Blocks:          {m.risk_blocks}",
            f"News Blocks:          {m.news_blocks}",
            f"Execution Failures:   {m.execution_failures}",
            f"Order Rejections:     {m.order_rejections}",
            f"Duplicate Orders:     {m.duplicate_orders}",
            "",
            "-- Performance --",
            f"Avg Detection:        {m.avg_detection_latency}ms",
            f"Avg Order:            {m.avg_order_latency}ms",
        ]
        if failed:
            lines.append("")
            lines.append("-- Failed Trades --")
            for t in failed[:10]:
                lines.append(f"  [{t.setup_id}] {t.symbol} {t.direction}: {t.fail_reason}")
            if len(failed) > 10:
                lines.append(f"  ... and {len(failed) - 10} more")
        lines.append("=" * 50)
        return "\n".join(lines)


harness = DemoValidationHarness()

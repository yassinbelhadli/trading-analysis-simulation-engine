from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Callable, Dict, List, Optional

from core_engine.health.health_models import (
    ComponentHealth,
    HealthStatus,
    SystemMetrics,
)
from core_engine.version import SYSTEM_VERSION

logger = logging.getLogger(__name__)

WARNING_TIMEOUT_SECONDS = 60.0
ERROR_TIMEOUT_SECONDS = 180.0


class HealthMonitor:
    def __init__(self):
        self._lock = Lock()
        self._components: Dict[str, ComponentHealth] = {}
        self._account_components: Dict[str, Dict[str, ComponentHealth]] = {}
        self._metrics = SystemMetrics()
        self._started_at: datetime = datetime.now(timezone.utc)
        self._listeners: List[Callable] = []
        self._running = False

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_component(self, component: str, account_id: Optional[str] = None,
                           version: str = "") -> None:
        health = ComponentHealth(version=version)
        with self._lock:
            if account_id:
                self._account_components.setdefault(account_id, {})[component] = health
            else:
                self._components[component] = health
        logger.info("Health component registered: %s (account=%s)", component, account_id)

    # ------------------------------------------------------------------
    # Heartbeat
    # ------------------------------------------------------------------

    def heartbeat(self, component: str, status: str = "HEALTHY",
                  message: str = "", latency_ms: float = 0.0,
                  account_id: Optional[str] = None) -> None:
        now = datetime.now(timezone.utc)
        with self._lock:
            health = self._get_component(component, account_id)
            if health is None:
                return
            if status == "HEALTHY":
                health.consecutive_failures = 0
            else:
                health.consecutive_failures += 1
            health.status = status
            health.last_seen = now
            health.latency_ms = latency_ms
            if message:
                health.message = message

    def _get_component(self, component: str,
                       account_id: Optional[str] = None) -> Optional[ComponentHealth]:
        if account_id:
            return self._account_components.get(account_id, {}).get(component)
        return self._components.get(component)

    # ------------------------------------------------------------------
    # Status queries
    # ------------------------------------------------------------------

    def get_component_status(self, component: str,
                             account_id: Optional[str] = None) -> Optional[ComponentHealth]:
        return self._get_component(component, account_id)

    def get_all_statuses(self) -> List[HealthStatus]:
        results: List[HealthStatus] = []
        now = datetime.now(timezone.utc)

        with self._lock:
            for name, ch in self._components.items():
                results.append(self._build_status(name, ch, now))
            for aid, comps in self._account_components.items():
                for name, ch in comps.items():
                    s = self._build_status(name, ch, now)
                    s.account_id = aid
                    results.append(s)
        return results

    def get_summary(self) -> Dict[str, Any]:
        statuses = self.get_all_statuses()
        healthy = sum(1 for s in statuses if s.status == "HEALTHY")
        warning = sum(1 for s in statuses if s.status == "WARNING")
        error = sum(1 for s in statuses if s.status == "ERROR")
        unknown = sum(1 for s in statuses if s.status == "UNKNOWN")

        return {
            "system_version": SYSTEM_VERSION,
            "uptime_seconds": (datetime.now(timezone.utc) - self._started_at).total_seconds(),
            "components": {
                "total": len(statuses),
                "healthy": healthy,
                "warning": warning,
                "error": error,
                "unknown": unknown,
            },
            "metrics": self._metrics.to_dict(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_json(self) -> Dict[str, Any]:
        statuses = self.get_all_statuses()
        by_status: Dict[str, list] = {"HEALTHY": [], "WARNING": [], "ERROR": [], "UNKNOWN": []}
        for s in statuses:
            by_status.setdefault(s.status, []).append({
                "component": s.component,
                "status": s.status,
                "message": s.message,
                "latency_ms": round(s.latency_ms, 1),
                "last_seen": s.last_seen.isoformat() if s.last_seen else None,
                "version": s.version or "",
                "account_id": s.account_id or "",
            })

        summary = self.get_summary()
        return {
            "summary": {
                "system_version": summary["system_version"],
                "uptime_seconds": round(summary["uptime_seconds"], 2),
                "components": summary["components"],
                "timestamp": summary["timestamp"],
            },
            "statuses": by_status,
            "metrics": self._metrics.to_dict(),
        }

    def _build_status(self, name: str, ch: ComponentHealth,
                      now: datetime) -> HealthStatus:
        elapsed = (now - ch.last_seen).total_seconds() if ch.last_seen else float("inf")
        if ch.status == "ERROR":
            computed = "ERROR"
        elif elapsed > ERROR_TIMEOUT_SECONDS:
            computed = "ERROR"
        elif elapsed > WARNING_TIMEOUT_SECONDS:
            computed = "WARNING"
        elif ch.status == "WARNING":
            computed = "WARNING"
        elif ch.status == "UNKNOWN" or ch.last_seen is None:
            computed = "UNKNOWN"
        else:
            computed = "HEALTHY"

        return HealthStatus(
            component=name,
            status=computed,
            last_seen=ch.last_seen or now,
            latency_ms=ch.latency_ms,
            message=ch.message or (f"No heartbeat for {elapsed:.0f}s" if elapsed > WARNING_TIMEOUT_SECONDS else ""),
            version=ch.version,
        )

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def increment_metric(self, name: str, value: int = 1) -> None:
        with self._lock:
            if hasattr(self._metrics, name):
                current = getattr(self._metrics, name)
                setattr(self._metrics, name, current + value)
                self._metrics.last_updated = datetime.now(timezone.utc)

    def record_latency(self, name: str, latency_ms: float) -> None:
        with self._lock:
            avg_attr = f"avg_{name}_time_ms"
            count_attr = f"_{name}_count"
            if hasattr(self._metrics, avg_attr):
                count = getattr(self, count_attr, 0) + 1
                setattr(self, count_attr, count)
                current_avg = getattr(self._metrics, avg_attr)
                new_avg = current_avg + (latency_ms - current_avg) / count
                setattr(self._metrics, avg_attr, new_avg)
                self._metrics.last_updated = datetime.now(timezone.utc)

    def set_metrics(self, metrics: Dict[str, Any]) -> None:
        with self._lock:
            for key, value in metrics.items():
                if hasattr(self._metrics, key):
                    setattr(self._metrics, key, value)
            self._metrics.last_updated = datetime.now(timezone.utc)

    def get_metrics(self) -> SystemMetrics:
        with self._lock:
            uptime = (datetime.now(timezone.utc) - self._started_at).total_seconds()
            self._metrics.uptime_seconds = uptime
            return self._metrics

    # ------------------------------------------------------------------
    # Listeners (for dashboard push)
    # ------------------------------------------------------------------

    def on_change(self, callback: Callable) -> None:
        self._listeners.append(callback)

    def start(self) -> None:
        self._running = True
        logger.info("HealthMonitor started")

    def stop(self) -> None:
        self._running = False
        logger.info("HealthMonitor stopped")


health_monitor = HealthMonitor()

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class HealthStatus:
    component: str
    status: str  # HEALTHY | WARNING | ERROR
    last_seen: datetime
    latency_ms: float
    message: str
    version: str = ""
    account_id: Optional[str] = None


@dataclass
class ComponentHealth:
    status: str = "UNKNOWN"  # HEALTHY | WARNING | ERROR | UNKNOWN
    last_seen: Optional[datetime] = None
    latency_ms: float = 0.0
    message: str = ""
    version: str = ""
    uptime_seconds: float = 0.0
    consecutive_failures: int = 0


@dataclass
class SystemMetrics:
    active_accounts: int = 0
    connected_accounts: int = 0
    paper_trades_today: int = 0
    real_trades_today: int = 0
    detection_cycles: int = 0
    orders_sent: int = 0
    orders_blocked: int = 0
    risk_breaches: int = 0
    avg_detection_time_ms: float = 0.0
    avg_execution_time_ms: float = 0.0
    avg_scanner_time_ms: float = 0.0
    uptime_seconds: float = 0.0
    last_updated: datetime = field(default_factory=_utcnow)

    def to_dict(self) -> dict:
        return {
            "active_accounts": self.active_accounts,
            "connected_accounts": self.connected_accounts,
            "paper_trades_today": self.paper_trades_today,
            "real_trades_today": self.real_trades_today,
            "detection_cycles": self.detection_cycles,
            "orders_sent": self.orders_sent,
            "orders_blocked": self.orders_blocked,
            "risk_breaches": self.risk_breaches,
            "avg_detection_time_ms": round(self.avg_detection_time_ms, 2),
            "avg_execution_time_ms": round(self.avg_execution_time_ms, 2),
            "avg_scanner_time_ms": round(self.avg_scanner_time_ms, 2),
            "uptime_seconds": round(self.uptime_seconds, 2),
            "last_updated": self.last_updated.isoformat(),
        }

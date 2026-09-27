from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class LifecycleStage(str, Enum):
    DETECTED = "DETECTED"
    PLANNED = "PLANNED"
    SENT = "SENT"
    FILLED = "FILLED"
    BE_MOVED = "BE_MOVED"
    PARTIAL_CLOSE = "PARTIAL_CLOSE"
    TRAILING_UPDATED = "TRAILING_UPDATED"
    CLOSED = "CLOSED"


# Allowed transitions between stages
ALLOWED_TRANSITIONS = {
    LifecycleStage.DETECTED: [LifecycleStage.PLANNED, LifecycleStage.SENT],
    LifecycleStage.PLANNED: [LifecycleStage.SENT],
    LifecycleStage.SENT: [LifecycleStage.FILLED, LifecycleStage.CLOSED],
    LifecycleStage.FILLED: [LifecycleStage.BE_MOVED, LifecycleStage.PARTIAL_CLOSE,
                            LifecycleStage.TRAILING_UPDATED, LifecycleStage.CLOSED],
    LifecycleStage.BE_MOVED: [LifecycleStage.PARTIAL_CLOSE, LifecycleStage.TRAILING_UPDATED,
                              LifecycleStage.CLOSED],
    LifecycleStage.PARTIAL_CLOSE: [LifecycleStage.BE_MOVED, LifecycleStage.TRAILING_UPDATED,
                                   LifecycleStage.CLOSED],
    LifecycleStage.TRAILING_UPDATED: [LifecycleStage.BE_MOVED, LifecycleStage.PARTIAL_CLOSE,
                                      LifecycleStage.CLOSED],
    LifecycleStage.CLOSED: [],
}

# Timeout between critical stages (seconds)
STAGE_TIMEOUTS = {
    LifecycleStage.DETECTED: 60,
    LifecycleStage.PLANNED: 30,
    LifecycleStage.SENT: 15,
    LifecycleStage.FILLED: 3600,
    LifecycleStage.BE_MOVED: 7200,
    LifecycleStage.PARTIAL_CLOSE: 7200,
    LifecycleStage.TRAILING_UPDATED: 7200,
}

CLOSING_STAGES = {LifecycleStage.CLOSED}
MANAGEMENT_STAGES = {LifecycleStage.BE_MOVED, LifecycleStage.PARTIAL_CLOSE, LifecycleStage.TRAILING_UPDATED}


@dataclass
class LifecycleStep:
    stage: LifecycleStage
    timestamp: datetime
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TradeLifecycle:
    account_id: str
    user_id: str
    setup_id: str
    ticket: Optional[str]
    symbol: str
    direction: str
    steps: List[LifecycleStep] = field(default_factory=list)
    failed: bool = False
    fail_reason: str = ""
    fail_stage: Optional[LifecycleStage] = None
    stale: bool = False

    @property
    def last_stage(self) -> Optional[LifecycleStage]:
        return self.steps[-1].stage if self.steps else None

    @property
    def last_time(self) -> Optional[datetime]:
        return self.steps[-1].timestamp if self.steps else None

    @property
    def elapsed_sec(self) -> float:
        if not self.steps:
            return 0.0
        return (datetime.now(timezone.utc) - self.steps[0].timestamp).total_seconds()

    @property
    def status(self) -> str:
        if self.failed:
            return f"FAILED@{self.fail_stage or '?'}: {self.fail_reason}"
        if self.stale:
            return f"STALE@{self.last_stage}"
        if not self.steps:
            return "NO_STEPS"
        stages = [s.stage for s in self.steps]
        if LifecycleStage.CLOSED in stages:
            return "COMPLETE"
        if LifecycleStage.FILLED in stages:
            return "ACTIVE"
        if LifecycleStage.SENT in stages:
            return "PENDING_FILL"
        if LifecycleStage.PLANNED in stages:
            return "PLANNED"
        return "DETECTED"

    def add_step(self, stage: LifecycleStage, data: Optional[Dict] = None) -> Optional[str]:
        if self.failed:
            return "ALREADY_FAILED"

        last = self.last_stage
        if last == stage:
            return None

        if last is not None and stage not in ALLOWED_TRANSITIONS.get(last, []):
            if stage in CLOSING_STAGES and last in MANAGEMENT_STAGES:
                pass
            elif last in MANAGEMENT_STAGES and stage in MANAGEMENT_STAGES:
                pass
            else:
                self.failed = True
                self.fail_reason = f"INVALID_TRANSITION: {last.value} -> {stage.value}"
                self.fail_stage = stage
                return self.fail_reason

        self.steps.append(LifecycleStep(stage=stage, timestamp=datetime.now(timezone.utc), data=data or {}))
        return None

    def mark_failed(self, reason: str, stage: Optional[LifecycleStage] = None):
        self.failed = True
        self.fail_reason = reason
        self.fail_stage = stage or self.last_stage

    def mark_stale(self):
        self.stale = True

    def timeout_stage(self) -> Optional[str]:
        last = self.last_stage
        if last is None or self.failed or self.stale or last == LifecycleStage.CLOSED:
            return None
        timeout = STAGE_TIMEOUTS.get(last)
        if timeout is None:
            return None
        last_time = self.last_time
        if last_time is None:
            return None
        elapsed = (datetime.now(timezone.utc) - last_time).total_seconds()
        if elapsed > timeout:
            return f"TIMEOUT@{last.value}: {elapsed:.0f}s > {timeout}s limit"
        return None


class LifecycleTracker:
    def __init__(self):
        self._trades: Dict[str, TradeLifecycle] = {}
        self._ticket_map: Dict[str, str] = {}
        self._failed: List[TradeLifecycle] = []
        self._stale: List[TradeLifecycle] = []
        self._total_setups: int = 0

    def track_setup(self, account_id: str, user_id: str, symbol: str, direction: str, setup_id: str, data: Optional[Dict] = None) -> str:
        self._total_setups += 1
        trade = TradeLifecycle(
            account_id=account_id, user_id=user_id,
            setup_id=setup_id, ticket=None,
            symbol=symbol, direction=direction,
        )
        trade.add_step(LifecycleStage.DETECTED, data)
        self._trades[setup_id] = trade
        return setup_id

    def track_planned(self, setup_id: str, data: Optional[Dict] = None) -> bool:
        return self._add_stage(setup_id, LifecycleStage.PLANNED, data)

    def track_sent(self, setup_id: str, data: Optional[Dict] = None) -> bool:
        return self._add_stage(setup_id, LifecycleStage.SENT, data)

    def track_filled(self, setup_id: str, ticket: str, data: Optional[Dict] = None) -> bool:
        trade = self._trades.get(setup_id)
        if trade:
            trade.ticket = ticket
            self._ticket_map[ticket] = setup_id
        return self._add_stage(setup_id, LifecycleStage.FILLED, data)

    def track_be(self, setup_id_or_ticket: str, data: Optional[Dict] = None) -> bool:
        return self._add_stage(setup_id_or_ticket, LifecycleStage.BE_MOVED, data)

    def track_partial(self, setup_id_or_ticket: str, data: Optional[Dict] = None) -> bool:
        return self._add_stage(setup_id_or_ticket, LifecycleStage.PARTIAL_CLOSE, data)

    def track_trailing(self, setup_id_or_ticket: str, data: Optional[Dict] = None) -> bool:
        return self._add_stage(setup_id_or_ticket, LifecycleStage.TRAILING_UPDATED, data)

    def track_closed(self, setup_id_or_ticket: str, data: Optional[Dict] = None) -> bool:
        return self._add_stage(setup_id_or_ticket, LifecycleStage.CLOSED, data)

    def _add_stage(self, setup_id_or_ticket: str, stage: LifecycleStage, data: Optional[Dict] = None) -> bool:
        trade = self._resolve(setup_id_or_ticket)
        if trade is None:
            return False
        err = trade.add_step(stage, data)
        if err:
            self._failed.append(trade)
        return True

    def mark_failed(self, setup_id_or_ticket: str, reason: str):
        trade = self._resolve(setup_id_or_ticket)
        if trade:
            trade.mark_failed(reason)
            self._failed.append(trade)

    def resolve(self, setup_id_or_ticket: str) -> Optional[TradeLifecycle]:
        return self._resolve(setup_id_or_ticket)

    def _resolve(self, key: str) -> Optional[TradeLifecycle]:
        trade = self._trades.get(key)
        if trade is None:
            sid = self._ticket_map.get(key)
            if sid:
                trade = self._trades.get(sid)
        return trade

    def get_trade(self, setup_id_or_ticket: str) -> Optional[TradeLifecycle]:
        return self._resolve(setup_id_or_ticket)

    def check_timeouts(self) -> List[str]:
        failures = []
        for trade in list(self._trades.values()):
            if trade.failed or trade.stale:
                continue
            timeout_msg = trade.timeout_stage()
            if timeout_msg:
                trade.mark_stale()
                self._stale.append(trade)
                failures.append(f"[{trade.setup_id}] {timeout_msg}")
        return failures

    def summary(self) -> Dict:
        all_trades = list(self._trades.values())
        total = len(all_trades)
        complete = sum(1 for t in all_trades if t.status == "COMPLETE")
        active = sum(1 for t in all_trades if t.status == "ACTIVE")
        failed = len(self._failed) + len(self._stale)
        pending = sum(1 for t in all_trades if t.status in ("PENDING_FILL", "PLANNED", "DETECTED"))

        return {
            "total": total,
            "total_setups": self._total_setups,
            "complete": complete,
            "active": active,
            "failed": failed,
            "pending": pending,
            "failure_count": len(self._failed),
            "stale_count": len(self._stale),
            "success_rate": round(complete / total * 100, 2) if total > 0 else 0,
        }

    def failed_trades(self) -> List[TradeLifecycle]:
        return self._failed + self._stale

    def all_trades(self) -> List[TradeLifecycle]:
        return list(self._trades.values())

    def reset(self):
        self._trades.clear()
        self._ticket_map.clear()
        self._failed.clear()
        self._stale.clear()
        self._total_setups = 0

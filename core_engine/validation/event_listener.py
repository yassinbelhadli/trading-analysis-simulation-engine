from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from core_engine.events.event_bus import event_bus
from core_engine.events.event_types import EventType
from core_engine.validation.lifecycle_tracker import LifecycleTracker, LifecycleStage

logger = logging.getLogger(__name__)


def _get_harness():
    from core_engine.validation.harness import harness
    return harness


class ValidationEventListener:
    def __init__(self, tracker: LifecycleTracker):
        self.tracker = tracker
        self._subscribed = False
        self._timestamps: Dict[str, float] = {}

    def subscribe_all(self):
        if self._subscribed:
            return
        self._subscribed = True

        callbacks = {
            # Engine publishes SETUP_DETECTED, not CANDIDATE_FOUND
            EventType.SETUP_DETECTED.value: self._on_candidate,
            EventType.PAPER_TRADE_PLANNED.value: self._on_planned,
            EventType.PAPER_TRADE_REJECTED.value: self._on_rejected,
            EventType.PAPER_TRADE_FILLED.value: self._on_filled,
            EventType.PAPER_TRADE_TP_HIT.value: self._on_tp_hit,
            EventType.PAPER_TRADE_SL_HIT.value: self._on_sl_hit,
            EventType.TRADE_OPENED.value: self._on_opened,
            EventType.BREAK_EVEN_MOVED.value: self._on_be,
            EventType.PARTIAL_CLOSE.value: self._on_partial,
            EventType.TRAILING_STOP_UPDATED.value: self._on_trailing,
            EventType.TRADE_CLOSED.value: self._on_closed,
            EventType.TRADE_BLOCKED.value: self._on_blocked,
            EventType.RISK_BREACH.value: self._on_risk_breach,
            EventType.ENGINE_STARTED.value: self._on_engine_event,
            EventType.ENGINE_STOPPED.value: self._on_engine_event,
            EventType.ENGINE_PAUSED.value: self._on_engine_event,
            EventType.ENGINE_ERROR.value: self._on_error,
            EventType.ERROR.value: self._on_error,
        }

        for event, cb in callbacks.items():
            event_bus.subscribe(event, cb)

        logger.info("ValidationEventListener subscribed to %d event types", len(callbacks))

    def unsubscribe_all(self):
        if not self._subscribed:
            return
        event_bus.clear()
        self._subscribed = False
        logger.info("ValidationEventListener unsubscribed")

    def _extract(self, data: Any) -> tuple:
        if data is None:
            data = {}
        if isinstance(data, dict):
            acct = str(data.get("account_id") or data.get("account") or "")
            uid = str(data.get("user_id") or "")
            sym = str(data.get("symbol") or "")
            direction = str(data.get("direction") or "")
            sid = str(data.get("setup_id") or data.get("candidate_id", data.get("id", "")))
            return acct, uid, sym, direction, sid, data
        return "", "", "", "", "", {}

    def _replay(self, event: str, data: Any, sid: str = "", account: str = ""):
        try:
            h = _get_harness()
            h.replay.write(event, data if isinstance(data, dict) else {}, account)
        except Exception:
            pass

    def _metrics(self):
        return _get_harness().metrics

    def _on_candidate(self, data: Any):
        acct, uid, sym, direction, sid, meta = self._extract(data)
        if sid:
            self.tracker.track_setup(acct, uid, sym, direction, sid, meta)
            self._metrics().signals_detected += 1
            self._timestamps[f"detect_{sid}"] = time.time()
        self._replay("CANDIDATE_FOUND", data, sid, acct)

    def _on_planned(self, data: Any):
        _, _, _, _, sid, meta = self._extract(data)
        if sid:
            self.tracker.track_planned(sid, meta)
            m = self._metrics()
            m.planned += 1
            t0 = self._timestamps.pop(f"detect_{sid}", None)
            if t0:
                m.detection_latencies.append(round((time.time() - t0) * 1000, 1))
        self._replay("PAPER_TRADE_PLANNED", data, sid)

    def _on_order_sent(self, data: Any):
        _, _, _, _, sid, meta = self._extract(data)
        if sid:
            self.tracker.track_sent(sid, meta)
            self._metrics().orders_sent += 1
            self._timestamps[f"sent_{sid}"] = time.time()
        self._replay("ORDER_SENT", data, sid)

    def _on_opened(self, data: Any):
        _, _, _, _, sid, meta = self._extract(data)
        ticket = str(meta.get("ticket", "")) if meta else ""
        if sid:
            self.tracker.track_filled(sid, ticket, meta)
            m = self._metrics()
            m.filled += 1
            m.lifecycle_complete += 1
            t0 = self._timestamps.pop(f"sent_{sid}", None)
            if t0:
                m.order_latencies.append(round((time.time() - t0) * 1000, 1))
        self._replay("TRADE_OPENED", data, sid)

    def _on_be(self, data: Any):
        _, _, _, _, sid, meta = self._extract(data)
        key = str(meta.get("ticket", "")) if meta else sid
        if self.tracker.track_be(key, meta):
            self._metrics().be_moved += 1
        self._replay("BREAK_EVEN_MOVED", data, key)

    def _on_partial(self, data: Any):
        _, _, _, _, sid, meta = self._extract(data)
        key = str(meta.get("ticket", "")) if meta else sid
        if self.tracker.track_partial(key, meta):
            self._metrics().partial_closed += 1
        self._replay("PARTIAL_CLOSE", data, key)

    def _on_trailing(self, data: Any):
        _, _, _, _, sid, meta = self._extract(data)
        key = str(meta.get("ticket", "")) if meta else sid
        if self.tracker.track_trailing(key, meta):
            self._metrics().trailing_updated += 1
        self._replay("TRAILING_STOP_UPDATED", data, key)

    def _on_closed(self, data: Any):
        _, _, _, _, sid, meta = self._extract(data)
        key = str(meta.get("ticket", "")) if meta else sid
        if self.tracker.track_closed(key, meta):
            reason = str(meta.get("reason", ""))
            m = self._metrics()
            if "TP" in reason.upper():
                m.tp_hit += 1
            elif "SL" in reason.upper():
                m.sl_hit += 1
        self._replay("TRADE_CLOSED", data, key)

    def _on_rejected(self, data: Any):
        _, _, _, _, sid, meta = self._extract(data)
        reason = str(meta.get("reason", "REJECTED")) if meta else "REJECTED"
        if sid:
            self.tracker.mark_failed(sid, reason)
            self._metrics().execution_failures += 1
        self._replay("PAPER_TRADE_REJECTED", data, sid)

    def _on_filled(self, data: Any):
        _, _, _, _, sid, meta = self._extract(data)
        ticket = str(meta.get("id", sid) if meta else sid)
        if sid:
            self.tracker.track_filled(sid, ticket, meta)
            self._metrics().filled += 1
            self._metrics().lifecycle_complete += 1
        self._replay("PAPER_TRADE_FILLED", data, sid)

    def _on_tp_hit(self, data: Any):
        _, _, _, _, sid, meta = self._extract(data)
        key = str(meta.get("id", sid) if meta else sid)
        if key:
            self.tracker.track_closed(key, {"reason": "TP_HIT"})
            self._metrics().tp_hit += 1
        self._replay("PAPER_TRADE_TP_HIT", data, key)

    def _on_sl_hit(self, data: Any):
        _, _, _, _, sid, meta = self._extract(data)
        key = str(meta.get("id", sid) if meta else sid)
        if key:
            self.tracker.track_closed(key, {"reason": "SL_HIT"})
            self._metrics().sl_hit += 1
        self._replay("PAPER_TRADE_SL_HIT", data, key)

    def _on_risk_breach(self, data: Any):
        _, _, _, _, sid, meta = self._extract(data)
        if sid:
            self.tracker.mark_failed(sid, "RISK_BREACH")
        self._replay("RISK_BREACH", data, sid)

    def _on_engine_event(self, data: Any):
        event = str(data.get("event_type", "ENGINE_EVENT")) if isinstance(data, dict) else "ENGINE_EVENT"
        self._replay(event, data)

    def _on_blocked(self, data: Any):
        _, _, _, _, sid, meta = self._extract(data)
        reason = str(meta.get("reason", "BLOCKED")) if meta else "BLOCKED"
        if sid:
            self.tracker.mark_failed(sid, reason)
            self._metrics().execution_failures += 1
        self._replay("TRADE_BLOCKED", data, sid)

    def _on_error(self, data: Any):
        msg = str(data) if data else "UNKNOWN_ERROR"
        logger.warning("Validation caught error event: %s", msg)
        self._replay("ERROR", data)

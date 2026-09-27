"""
Subscribes to event bus events and updates HealthMonitor metrics.

Auto-started along with AuditLogger.
"""

from __future__ import annotations

import logging
from typing import Any

from core_engine.events.event_bus import event_bus
from core_engine.events.event_types import EventType
from core_engine.health.health_monitor import health_monitor

logger = logging.getLogger(__name__)


class HealthHooks:
    def __init__(self):
        self._subscribed = False

    def start(self):
        if self._subscribed:
            return
        subscriptions = {
            EventType.TRADE_CREATED: self._on_trade_created,
            EventType.TRADE_OPENED: self._on_trade_opened,
            EventType.TRADE_BLOCKED: self._on_trade_blocked,
            EventType.ORDER_SENT: self._on_order_sent,
            EventType.RISK_BREACH: self._on_risk_breach,
            EventType.ACCOUNT_CONNECTED: self._on_account_connected,
            EventType.ACCOUNT_DISCONNECTED: self._on_account_disconnected,
            EventType.SETUP_DETECTED: self._on_setup_detected,
            EventType.CANDIDATE_FOUND: self._on_setup_detected,
            EventType.ENGINE_ERROR: self._on_engine_error,
            EventType.HEALTH_WARNING: self._on_health_warning,
        }
        for ev_type, callback in subscriptions.items():
            event_bus.subscribe(ev_type.value, callback)

        self._subscribed = True
        logger.info("HealthHooks subscribed to %d event types", len(subscriptions))

    def stop(self):
        if not self._subscribed:
            return
        for ev_type in EventType:
            event_bus.unsubscribe(ev_type.value, self._on_event)
        self._subscribed = False

    def _on_event(self, data: Any):
        pass

    def _on_trade_created(self, data: Any):
        if isinstance(data, dict):
            is_paper = data.get("data", {}).get("is_paper", False)
            if is_paper:
                health_monitor.increment_metric("paper_trades_today")
            else:
                health_monitor.increment_metric("real_trades_today")

    def _on_trade_opened(self, data: Any):
        health_monitor.increment_metric("connected_accounts")

    def _on_trade_blocked(self, data: Any):
        health_monitor.increment_metric("orders_blocked")

    def _on_order_sent(self, data: Any):
        health_monitor.increment_metric("orders_sent")

    def _on_risk_breach(self, data: Any):
        health_monitor.increment_metric("risk_breaches")

    def _on_account_connected(self, data: Any):
        health_monitor.increment_metric("connected_accounts")

    def _on_account_disconnected(self, data: Any):
        connected = max(0, health_monitor._metrics.connected_accounts - 1)
        health_monitor.set_metrics({"connected_accounts": connected})

    def _on_setup_detected(self, data: Any):
        pass

    def _on_engine_error(self, data: Any):
        if isinstance(data, dict):
            account_id = data.get("account_id")
            health_monitor.heartbeat(
                component=f"EngineRunner:{account_id}" if account_id else "EngineRunner",
                status="ERROR",
                message=data.get("message", "Engine error"),
                account_id=account_id,
            )

    def _on_health_warning(self, data: Any):
        if isinstance(data, dict):
            account_id = data.get("account_id")
            component = data.get("component", "system")
            health_monitor.heartbeat(
                component=component,
                status="WARNING",
                message=data.get("message", "Health warning"),
                account_id=account_id,
            )


health_hooks = HealthHooks()

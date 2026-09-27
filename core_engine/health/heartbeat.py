from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from core_engine.health.health_monitor import health_monitor

logger = logging.getLogger(__name__)


class HeartbeatSender:
    """
    Mixin for any service that wants to send periodic heartbeats.

    Call start_heartbeat(component_name, interval_seconds) in the service's start method.
    The service should also call send_heartbeat() manually after each successful operation.
    """

    def __init__(self):
        self._hb_component: str = ""
        self._hb_interval: float = 15.0
        self._hb_task: Optional[asyncio.Task] = None
        self._hb_account_id: Optional[str] = None
        self._hb_version: str = ""
        self._running = False

    def start_heartbeat(self, component: str, interval: float = 15.0,
                        account_id: Optional[str] = None,
                        version: str = "") -> None:
        self._hb_component = component
        self._hb_interval = interval
        self._hb_account_id = account_id
        self._hb_version = version
        self._running = True

        health_monitor.register_component(
            component, account_id=account_id, version=version,
        )

        if self._hb_task is None or self._hb_task.done():
            self._hb_task = asyncio.create_task(self._heartbeat_loop())
            logger.debug("Heartbeat loop started for %s (%.1fs)", component, interval)

    async def stop_heartbeat(self) -> None:
        self._running = False
        if self._hb_task and not self._hb_task.done():
            self._hb_task.cancel()
            try:
                await self._hb_task
            except asyncio.CancelledError:
                pass
            self._hb_task = None

    def send_heartbeat(self, status: str = "HEALTHY", message: str = "",
                       latency_ms: float = 0.0, account_id: Optional[str] = None) -> None:
        health_monitor.heartbeat(
            component=self._hb_component,
            status=status,
            message=message or f"{self._hb_component} running",
            latency_ms=latency_ms,
            account_id=account_id or self._hb_account_id,
        )

    async def _heartbeat_loop(self) -> None:
        while self._running:
            try:
                self.send_heartbeat()
                await asyncio.sleep(self._hb_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("Heartbeat error for %s: %s", self._hb_component, e)
                await asyncio.sleep(self._hb_interval)

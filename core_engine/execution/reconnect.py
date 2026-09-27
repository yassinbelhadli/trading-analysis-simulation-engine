"""Reconnection manager — maintains broker connection with heartbeat."""

from __future__ import annotations
import time
import logging
from typing import Optional, Callable

from .errors import ConnectionError

logger = logging.getLogger(__name__)


class ReconnectManager:
    """Manages broker reconnection with heartbeat and state tracking.

    Usage:
        rm = ReconnectManager(connect_fn=lambda: mt5.initialize())
        connected = rm.ensure_connected()
    """

    def __init__(
        self,
        connect_fn: Callable[[], bool],
        disconnect_fn: Optional[Callable] = None,
        max_retries: int = 5,
        base_delay: float = 1.0,
        heartbeat_interval: float = 30.0,
    ):
        self._connect = connect_fn
        self._disconnect = disconnect_fn
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.heartbeat_interval = heartbeat_interval
        self._connected = False
        self._last_heartbeat = 0.0

    @property
    def is_connected(self) -> bool:
        return self._connected

    def connect(self) -> bool:
        """Initial connection attempt."""
        try:
            self._connected = bool(self._connect())
            if self._connected:
                self._last_heartbeat = time.time()
                logger.info("Broker connected")
            else:
                logger.error("Broker connection failed")
            return self._connected
        except Exception as e:
            logger.error("Broker connection error: %s", e)
            self._connected = False
            return False

    def disconnect(self):
        """Graceful disconnect."""
        if self._disconnect:
            try:
                self._disconnect()
            except Exception as e:
                logger.warning("Disconnect error: %s", e)
        self._connected = False
        logger.info("Broker disconnected")

    def ensure_connected(self) -> bool:
        """Ensure connection is alive. Reconnect if needed.

        Returns:
            True if connected after attempt.
        """
        if self._connected:
            # Heartbeat check
            if time.time() - self._last_heartbeat > self.heartbeat_interval:
                if not self._heartbeat():
                    logger.warning("Heartbeat failed, reconnecting...")
                    self._connected = False
                else:
                    self._last_heartbeat = time.time()
                    return True

        if not self._connected:
            return self._reconnect()

        return self._connected

    def _heartbeat(self) -> bool:
        """Check if connection is alive (override in broker adapter)."""
        return self._connected

    def _reconnect(self) -> bool:
        """Reconnect with exponential backoff."""
        for attempt in range(1, self.max_retries + 1):
            delay = self.base_delay * (2 ** (attempt - 1))
            logger.info("Reconnect attempt %d/%d in %.1fs...", attempt, self.max_retries, delay)
            time.sleep(delay)
            try:
                self._connected = bool(self._connect())
                if self._connected:
                    self._last_heartbeat = time.time()
                    logger.info("Reconnected successfully")
                    return True
            except Exception as e:
                logger.warning("Reconnect attempt %d failed: %s", attempt, e)

        logger.error("All reconnect attempts exhausted")
        self._connected = False
        return False

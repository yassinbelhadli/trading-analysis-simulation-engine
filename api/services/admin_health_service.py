from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Optional

from core_engine.engine_manager import engine_manager
from core_engine.health.health_monitor import health_monitor

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[2]
HEARTBEAT_PATH = BASE_DIR / "logs" / "heartbeat.json"
HEALTH_REPORT_PATH = BASE_DIR / "logs" / "health_report.json"
NEWS_CACHE_PATH = BASE_DIR / "data" / "processed" / "news_cache.csv"


def _read_json(path: Path) -> dict:
    try:
        if path.exists():
            with open(str(path)) as f:
                return json.load(f)
    except Exception as e:
        logger.warning("Failed to read %s: %s", path.name, e)
    return {}


class AdminHealthService:
    """Centralised source for health, heartbeat and engine data.

    All admin health routes read through this service so the data
    source can be swapped (DB / Redis / live poll) without touching routes.
    """

    @staticmethod
    def get_health_json() -> dict:
        """Live health monitor snapshot (in-memory counters + component statuses)."""
        return health_monitor.get_json()

    @staticmethod
    def get_health_summary() -> dict:
        return health_monitor.get_summary()

    @staticmethod
    def get_heartbeat() -> dict:
        return _read_json(HEARTBEAT_PATH)

    @staticmethod
    def get_health_report() -> dict:
        return _read_json(HEALTH_REPORT_PATH)

    @staticmethod
    def get_engines() -> list:
        return engine_manager.list_statuses()

    @staticmethod
    def get_engine_status(account_id: str) -> Optional[dict]:
        return engine_manager.get_status(account_id)

    @staticmethod
    def get_overview_engine() -> dict:
        """Combined engine block used by the /overview endpoint."""
        hb = _read_json(HEARTBEAT_PATH) or {}
        hr = _read_json(HEALTH_REPORT_PATH) or {}
        return {
            "pid": hb.get("pid"),
            "instance_id": hb.get("instance_id"),
            "started_at": hb.get("started_at") or hr.get("started_at"),
            "uptime_hours": hr.get("uptime_hours"),
            "status": hb.get("status", "UNKNOWN"),
            "cycles": hb.get("cycles") or hr.get("cycles"),
            "mt5_connected": hb.get("mt5_connected") or hr.get("mt5_connected", False),
            "telegram_connected": hr.get("telegram_connected", False),
            "heartbeat_age_sec": hr.get("heartbeat_age_sec"),
            "memory_mb": hr.get("memory_mb"),
            "cpu_percent": hr.get("cpu_percent"),
            "active_trades": hr.get("active_trades", 0),
        }

    @staticmethod
    def get_integrations() -> dict:
        """Phase 6.0 integration component registry — email / telegram / billing /
        news / engine status. Only configuration *presence* is reported (no
        secrets, no real provider pings until those channels are productionised)."""
        from config.settings import (
            BOT_USERNAME,
            SMTP_HOST,
            SMTP_PASS,
            SMTP_USER,
            TELEGRAM_BOT_TOKEN,
        )

        hb = _read_json(HEARTBEAT_PATH) or {}

        news_status = "not_configured"
        last_fetch_ago_sec = None
        if NEWS_CACHE_PATH.exists():
            mtime = NEWS_CACHE_PATH.stat().st_mtime
            last_fetch_ago_sec = int(time.time() - mtime)
            news_status = "running" if last_fetch_ago_sec < 7200 else "stale"

        engine_status = hb.get("status", "UNKNOWN")
        heartbeat_age_sec = None
        try:
            last = hb.get("last_heartbeat_utc")
            if last:
                from datetime import datetime, timezone
                hb_time = datetime.fromisoformat(str(last))
                heartbeat_age_sec = int(
                    (datetime.now(timezone.utc) - hb_time).total_seconds()
                )
        except Exception:
            pass

        email_configured = bool(SMTP_USER and SMTP_PASS)

        return {
            "email": {
                "channel": "email",
                "status": "configured" if email_configured else "not_configured",
                "configured": email_configured,
                "smtp_host": SMTP_HOST,
            },
            "telegram": {
                "channel": "telegram",
                "status": "configured" if TELEGRAM_BOT_TOKEN else "not_configured",
                "configured": bool(TELEGRAM_BOT_TOKEN),
                "bot_username": BOT_USERNAME,
            },
            "billing": {
                "channel": "billing",
                "status": "not_configured",
                "configured": False,
                "provider": None,
            },
            "news": {
                "channel": "news",
                "status": news_status,
                "last_fetch_ago_sec": last_fetch_ago_sec,
            },
            "engine": {
                "channel": "engine",
                "status": engine_status,
                "heartbeat_age_sec": heartbeat_age_sec,
            },
        }

    @staticmethod
    async def control_engine(action: str) -> str:
        tasks = []
        for aid in list(engine_manager._engines.keys()):
            if action == "restart":
                tasks.append(engine_manager.restart(aid))
            elif action == "stop":
                tasks.append(engine_manager.stop(aid))
            elif action == "start":
                tasks.append(engine_manager.start(aid))
        if tasks:
            import asyncio
            await asyncio.gather(*tasks, return_exceptions=True)
        return f"Engine {action} requested"

    @staticmethod
    def restart_service(service: str) -> dict:
        """Acknowledge a restart request honestly.

        There is no process manager in this deployment yet (no supervisor /
        systemd), so an in-process restart is unsafe. The request is audited and
        marked unsupported — the UI must surface this instead of pretending a
        restart happened. Phase 6.2 introduces real restart wiring when a
        process manager exists.
        """
        logger.warning("Restart request for '%s' received — unsupported (no process manager)", service)
        return {
            "service": service,
            "supported": False,
            "message": f"{service} restart not supported: no process manager in this deployment",
        }


admin_health_service = AdminHealthService()

"""
Background Runner v2 — Engine 24/7, fully detached.

No stdout/stderr output. All logging to rotating files.
JSON heartbeat written atomically every 30s.
JSON health report written atomically every 60min.

Usage:
    cmd /c start "" "python.exe" -m scripts.background_runner
"""
import json
import logging
import logging.handlers
import os
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
os.chdir(str(ROOT))
sys.path.insert(0, str(ROOT))

# --- File logging only ---
LOGS_DIR = ROOT / "logs"
LOGS_DIR.mkdir(exist_ok=True)

ENGINE_LOG = str(LOGS_DIR / "engine.log")
HEARTBEAT_FILE = LOGS_DIR / "heartbeat.json"
HEALTH_REPORT_FILE = LOGS_DIR / "health_report.json"
PID_FILE = LOGS_DIR / "background_runner.pid"

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
for h in root_logger.handlers[:]:
    root_logger.removeHandler(h)

handler = logging.handlers.RotatingFileHandler(
    ENGINE_LOG, maxBytes=50 * 1024 * 1024, backupCount=3
)
handler.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
)
root_logger.addHandler(handler)
logging.captureWarnings(True)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

logger = logging.getLogger("background_runner")


def _atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False
    ) as tmp:
        json.dump(data, tmp, ensure_ascii=False, indent=2)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


try:
    from core_engine.version import ENGINE_VERSION
except ImportError:
    ENGINE_VERSION = "unknown"

VERSION: str = ENGINE_VERSION
INSTANCE_ID: str = uuid.uuid4().hex[:12]
STARTED_AT: str = datetime.now(timezone.utc).isoformat()


def write_heartbeat(payload: dict) -> None:
    try:
        data = {
            "version": VERSION,
            "pid": os.getpid(),
            "instance_id": INSTANCE_ID,
            "started_at": STARTED_AT,
            "status": payload.get("status", "RUNNING"),
            "cycles": payload.get("cycles", 0),
            "mt5_connected": payload.get("mt5_connected", False),
            "last_heartbeat_utc": datetime.now(timezone.utc).isoformat(),
        }
        _atomic_write_json(HEARTBEAT_FILE, data)
    except Exception as exc:
        logger.warning("Heartbeat write failed: %s", exc)


def write_health_report(report: dict) -> None:
    try:
        report["version"] = VERSION
        report["instance_id"] = INSTANCE_ID
        report["started_at"] = STARTED_AT
        report["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
        report["pid"] = os.getpid()
        _atomic_write_json(HEALTH_REPORT_FILE, report)
    except Exception as exc:
        logger.warning("Health report write failed: %s", exc)


# --- Write PID file from the engine process itself ---
try:
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
except Exception as exc:
    logger.warning("PID file write failed: %s", exc)

# --- Initial heartbeat ---
write_heartbeat({"status": "STARTING", "cycles": 0, "mt5_connected": False})
logger.info("=" * 60)
logger.info("BACKGROUND RUNNER v2")
logger.info("Start:  %s", datetime.now(timezone.utc).isoformat())
logger.info("PID:    %d", os.getpid())
logger.info("Log:    %s", ENGINE_LOG)
logger.info("=" * 60)

# --- Override print to go through logging (catch detector ASCII output) ---
import builtins

_real_print = builtins.print

def _log_print(*args, **kwargs):
    logger.debug(" ".join(str(a) for a in args))

builtins.print = _log_print

# --- Redirect sys.stdout/stderr to null (kill any console dependency) ---
sys.stdout = open(os.devnull, "w", encoding="utf-8")
sys.stderr = open(os.devnull, "w", encoding="utf-8")

# --- Import engine ---
import asyncio
import psutil
from backtester.demo_validation import DemoValidationApp


class HeartbeatDemoApp(DemoValidationApp):
    """Extends DemoValidationApp with periodic heartbeat + hourly health report."""

    def __init__(self):
        super().__init__()
        self._hb_task: Optional[asyncio.Task] = None
        self._hr_task: Optional[asyncio.Task] = None
        self._started_at = datetime.now(timezone.utc)
        logger.info("Instance ID: %s", INSTANCE_ID)

    async def _heartbeat_loop(self):
        while True:
            try:
                cycles = 0
                mt5_ok = False
                try:
                    from core_engine.engine_runner import engine_runner
                    cycles = engine_runner._debug_counters.get("cycles", 0)
                except Exception:
                    pass
                try:
                    import MetaTrader5 as mt5
                    mt5_ok = mt5.terminal_info() is not None
                except Exception:
                    pass
                write_heartbeat({
                    "status": "RUNNING",
                    "cycles": cycles,
                    "mt5_connected": mt5_ok,
                })
            except Exception:
                pass
            await asyncio.sleep(30)

    async def _health_report_loop(self):
        await asyncio.sleep(300)
        write_health_report(await self._collect_health_data())
        logger.info("Initial health report written")
        while True:
            try:
                report = await self._collect_health_data()
                write_health_report(report)
                logger.info("Health report: uptime=%.1fh cycles=%d active=%d natural=%d stale=%d",
                            report["uptime_hours"], report["cycles"],
                            report["active_trades"], report["natural_closed"],
                            report["stale_cleanup"])
            except Exception as exc:
                logger.warning("Health report failed: %s", exc)
            await asyncio.sleep(3600)

    async def _collect_health_data(self) -> dict:
        uptime_hours = round(
            (datetime.now(timezone.utc) - self._started_at).total_seconds() / 3600, 1
        )

        cycles = 0
        setups_found = 0
        published = 0
        try:
            from core_engine.engine_runner import engine_runner
            cycles = engine_runner._debug_counters.get("cycles", 0)
            setups_found = engine_runner._debug_counters.get("setups_found", 0)
            published = engine_runner._debug_counters.get("setups_published", 0)
        except Exception:
            pass

        mt5_ok = False
        try:
            import MetaTrader5 as mt5
            mt5_ok = mt5.terminal_info() is not None
        except Exception:
            pass

        telegram_ok = False
        try:
            if self.app and self.app.bot:
                token = getattr(self.app.bot, "token", None)
                telegram_ok = token is not None and len(token) > 20
        except Exception:
            pass

        memory_mb = 0
        cpu_percent = 0.0
        try:
            proc = psutil.Process(os.getpid())
            memory_mb = round(proc.memory_info().rss / 1024 / 1024, 1)
            cpu_percent = proc.cpu_percent(interval=0.2)
        except Exception:
            pass

        heartbeat_age_sec = -1
        try:
            hb_data = json.loads(HEARTBEAT_FILE.read_text(encoding="utf-8"))
            hb_time = datetime.fromisoformat(hb_data["last_heartbeat_utc"])
            heartbeat_age_sec = round(
                (datetime.now(timezone.utc) - hb_time).total_seconds()
            )
        except Exception:
            pass

        active_trades = 0
        natural_closed = 0
        stale_cleanup = 0
        try:
            from database.db import async_session_factory
            from database.models import PaperTrade, TradeStatus
            from sqlalchemy import select, func

            async with async_session_factory() as session:
                r = await session.execute(
                    select(func.count()).where(
                        PaperTrade.status.in_([TradeStatus.PLANNED, TradeStatus.FILLED])
                    )
                )
                active_trades = r.scalar() or 0

                r = await session.execute(
                    select(func.count()).where(
                        PaperTrade.close_category.in_(["NATURAL_TP", "NATURAL_SL"])
                    )
                )
                natural_closed = r.scalar() or 0

                r = await session.execute(
                    select(func.count()).where(
                        PaperTrade.close_category == "STALE_CLEANUP"
                    )
                )
                stale_cleanup = r.scalar() or 0
        except Exception:
            pass

        return {
            "uptime_hours": uptime_hours,
            "cycles": cycles,
            "setups_found": setups_found,
            "published": published,
            "active_trades": active_trades,
            "natural_closed": natural_closed,
            "stale_cleanup": stale_cleanup,
            "mt5_connected": mt5_ok,
            "telegram_connected": telegram_ok,
            "heartbeat_age_sec": heartbeat_age_sec,
            "memory_mb": memory_mb,
            "cpu_percent": cpu_percent,
        }

    async def _post_init(self, app):
        loop = asyncio.get_event_loop()
        self._hb_task = loop.create_task(self._heartbeat_loop())
        self._hr_task = loop.create_task(self._health_report_loop())
        logger.info("Heartbeat loop started (every 30s)")
        logger.info("Health report loop started (every 60min)")
        return await super()._post_init(app)

    async def _post_shutdown(self, app):
        if self._hb_task and not self._hb_task.done():
            self._hb_task.cancel()
        if self._hr_task and not self._hr_task.done():
            self._hr_task.cancel()
        write_heartbeat({"status": "STOPPED", "cycles": 0, "mt5_connected": False})
        return await super()._post_shutdown(app)


app = HeartbeatDemoApp()

try:
    app.run()
except KeyboardInterrupt:
    logger.info("Received KeyboardInterrupt")
except Exception:
    logger.exception("FATAL — background runner crashed")
    write_heartbeat({"status": "CRASHED", "cycles": 0, "mt5_connected": False})
    raise
finally:
    logger.info("Stopped at %s", datetime.now(timezone.utc).isoformat())
    write_heartbeat({"status": "STOPPED", "cycles": 0, "mt5_connected": False})

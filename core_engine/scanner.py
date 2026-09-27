from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from database.db import async_session_factory
from database.repositories import AccountRepository, ScanRepository
from database.models import AccountScan
from core_engine.account_manager import AccountManager
from core_engine.risk_manager import RiskManager
from database.models import RiskProfile
from core_engine.mt_runtime import (
    MTRuntime,
    MTConnectionConfig,
    create_mt_runtime,
    MTPosition,
    MTOrder,
    MTRuntimeError,
)
from core_engine.engine_manager import engine_manager
from core_engine.events.event_bus import event_bus
from core_engine.events.event_types import EventType
from core_engine.health.heartbeat import HeartbeatSender
from core_engine.health.health_monitor import health_monitor
from core_engine.version import ENGINE_VERSION

logger = logging.getLogger(__name__)


@dataclass
class ScanResult:
    account_id: str
    success: bool
    balance: Optional[float] = None
    equity: Optional[float] = None
    margin: Optional[float] = None
    margin_free: Optional[float] = None
    margin_level: Optional[float] = None
    positions: List[MTPosition] = field(default_factory=list)
    orders: List[MTOrder] = field(default_factory=list)
    symbols: List[str] = field(default_factory=list)
    breaches: List[dict] = field(default_factory=list)
    connection_ok: bool = True
    error: Optional[str] = None
    scanned_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class AccountScanner(HeartbeatSender):
    def __init__(self, scan_interval: float = 3.0, reconnect_delay: float = 10.0):
        super().__init__()
        self.scan_interval = scan_interval
        self.reconnect_delay = reconnect_delay
        self._tasks: Dict[str, asyncio.Task] = {}
        self._runtimes: Dict[str, MTRuntime] = {}
        self._running = False

    async def _ensure_runtime(self, account_id: str) -> Optional[MTRuntime]:
        existing = self._runtimes.get(account_id)
        if existing and existing.connected:
            return existing

        if existing:
            try:
                await existing.disconnect()
            except Exception:
                pass

        async with async_session_factory() as session:
            repo = AccountRepository(session)
            account = await repo.get_by_id(account_id)
            if not account or not account.server or not account.login:
                return None

            password = ""
            if account.encrypted_password:
                try:
                    from security.encryption import decrypt
                    password = decrypt(account.encrypted_password)
                except Exception:
                    logger.warning("Password decryption failed for %s, using empty", account_id)

            config = MTConnectionConfig(
                server=account.server,
                login=account.login,
                password=password,
                platform=account.platform or "MT5",
            )
            mt = create_mt_runtime(config)
            ok = await mt.connect()
            if not ok:
                logger.error("MT5 connect failed for %s", account_id)
                event_bus.publish(EventType.ACCOUNT_DISCONNECTED.value, {
                    "event_type": EventType.ACCOUNT_DISCONNECTED.value,
                    "account_id": account_id,
                    "user_id": account.user_id,
                    "message": f"MT5 connect failed for {account_id}",
                })
                return None
            self._runtimes[account_id] = mt

            event_bus.publish(EventType.ACCOUNT_CONNECTED.value, {
                "event_type": EventType.ACCOUNT_CONNECTED.value,
                "account_id": account_id,
                "user_id": account.user_id,
                "message": f"Account {account_id} connected to MT5",
            })
            return mt

    async def scan_account(self, account_id: str) -> ScanResult:
        mt = None
        try:
            mt = await self._ensure_runtime(account_id)
            if not mt:
                return ScanResult(account_id=account_id, success=False,
                                  error="MT connection failed", connection_ok=False)

            acc_info = await mt.account_info()
            positions = await mt.get_positions()
            orders = await mt.get_orders()
            symbols_raw = await mt.get_symbols()

            balance = acc_info.balance
            equity = acc_info.equity

            async with async_session_factory() as session:
                acc_mgr = AccountManager(session)
                risk_mgr = RiskManager(session)

                risk_snapshot = await acc_mgr.update_drawdown(account_id, balance, equity)
                day_start = risk_snapshot.get("day_start_equity") or equity

                # threshold warnings (80%, 90%, 100%)
                account = await acc_mgr.get_account(account_id)
                risk_profile: RiskProfile = account.risk_profile if account else None
                if risk_profile:
                    dl_limit = risk_profile.daily_loss or 5.0
                    ml_limit = risk_profile.max_loss or 15.0
                    dl_pct = risk_profile.current_daily_loss_pct or 0.0
                    ml_pct = risk_profile.current_max_loss_pct or 0.0

                    dl_ratio = dl_pct / dl_limit if dl_limit > 0 else 0
                    ml_ratio = ml_pct / ml_limit if ml_limit > 0 else 0

                    for ratio, level in [(0.80, "warning"), (0.90, "critical")]:
                        if dl_ratio >= ratio and dl_ratio < 1.0:
                            event_bus.publish(EventType.HEALTH_WARNING.value, {
                                "event_type": EventType.HEALTH_WARNING.value,
                                "account_id": account_id,
                                "user_id": account.user_id if account else None,
                                "message": f"Daily Loss {level}: {dl_pct}% / {dl_limit}%",
                                "data": {"current_pct": dl_pct, "limit_pct": dl_limit},
                            })
                        if ml_ratio >= ratio and ml_ratio < 1.0:
                            event_bus.publish(EventType.HEALTH_WARNING.value, {
                                "event_type": EventType.HEALTH_WARNING.value,
                                "account_id": account_id,
                                "user_id": account.user_id if account else None,
                                "message": f"Max Loss {level}: {ml_pct}% / {ml_limit}%",
                                "data": {"current_pct": ml_pct, "limit_pct": ml_limit},
                            })

                breaches = await risk_mgr.detect_breaches(
                    account_id=account_id,
                    current_equity=equity,
                    daily_start_equity=day_start,
                )

                scan = AccountScan(
                    account_id=account_id,
                    balance_detected=balance,
                    equity_detected=equity,
                    symbols_detected=",".join(s.name for s in symbols_raw),
                    scan_status="breach" if breaches else "ok",
                )
                session.add(scan)
                await session.commit()

            if breaches:
                logger.warning("Breaches detected for %s: %s", account_id,
                               [b["type"] for b in breaches])

            return ScanResult(
                account_id=account_id,
                success=True,
                balance=balance,
                equity=equity,
                margin=acc_info.margin,
                margin_free=acc_info.margin_free,
                margin_level=acc_info.margin_level,
                positions=positions,
                orders=orders,
                symbols=[s.name for s in symbols_raw],
                breaches=breaches,
                connection_ok=True,
            )

        except MTRuntimeError as e:
            logger.error("MT5 runtime error for %s: %s", account_id, e)
            return ScanResult(account_id=account_id, success=False,
                              error=str(e), connection_ok=False)

        except Exception as e:
            logger.exception("Scan failed for %s", account_id)
            return ScanResult(account_id=account_id, success=False,
                              error=str(e))

        finally:
            if mt:
                pass

    async def _scan_loop(self, account_id: str):
        logger.info("Scanner started for %s", account_id)
        event_bus.publish(EventType.SCANNER_STARTED.value, {
            "event_type": EventType.SCANNER_STARTED.value,
            "account_id": account_id,
            "user_id": None,
            "message": f"Scanner started for account {account_id}",
        })
        consecutive_failures = 0
        try:
            while self._running:
                t0 = time.monotonic()

                # Always update drawdown (risk tracking runs even when engine is stopped)
                mt = await self._ensure_runtime(account_id)
                if mt:
                    try:
                        acc_info = await mt.account_info()
                        balance = acc_info.balance
                        equity = acc_info.equity
                        async with async_session_factory() as session:
                            acc_mgr = AccountManager(session)
                            await acc_mgr.update_drawdown(account_id, balance, equity)
                            await session.commit()
                    except Exception:
                        logger.exception("Drawdown update failed for %s", account_id)

                # Full scan only when engine is running
                if not engine_manager.is_running(account_id):
                    elapsed_ms = (time.monotonic() - t0) * 1000
                    health_monitor.record_latency("scanner", elapsed_ms)
                    self.send_heartbeat(
                        status="IDLE",
                        latency_ms=elapsed_ms,
                        message=f"Scanner idle for {account_id} (engine stopped)",
                        account_id=account_id,
                    )
                    await asyncio.sleep(self.scan_interval)
                    continue

                result = await self.scan_account(account_id)
                elapsed_ms = (time.monotonic() - t0) * 1000

                health_monitor.record_latency("scanner", elapsed_ms)
                self.send_heartbeat(
                    status="ERROR" if not result.success else "HEALTHY",
                    latency_ms=elapsed_ms,
                    message=f"Scanner loop for {account_id}",
                    account_id=account_id,
                )

                if not result.connection_ok:
                    consecutive_failures += 1
                    delay = min(self.reconnect_delay * consecutive_failures, 60.0)
                    logger.warning("Scan %s: connection lost, retry in %.0fs (attempt %d)",
                                   account_id, delay, consecutive_failures)
                    await asyncio.sleep(delay)
                    continue
                consecutive_failures = 0

                if result.success:
                    engine_manager.heartbeat(account_id)

                if result.breaches:
                    async with async_session_factory() as session:
                        acc_mgr = AccountManager(session)
                        await acc_mgr.pause_account(account_id)
                        await session.commit()

                    breach_types = [b["type"] for b in result.breaches]
                    engine_manager.set_error(account_id, f"Risk breach: {breach_types}")

                    health_monitor.increment_metric("risk_breaches")

                    event_bus.publish(EventType.RISK_BREACH.value, {
                        "event_type": EventType.RISK_BREACH.value,
                        "account_id": account_id,
                        "user_id": None,
                        "message": f"Risk breach: {', '.join(breach_types)}",
                        "data": {"breaches": result.breaches},
                    })

                await asyncio.sleep(self.scan_interval)
        except asyncio.CancelledError:
            logger.info("Scanner cancelled for %s", account_id)
            raise
        except Exception:
            logger.exception("Scanner loop crashed for %s", account_id)
            raise

    async def start_scanning(self, account_id: str) -> None:
        if account_id in self._tasks and not self._tasks[account_id].done():
            logger.warning("Scanner already running for %s", account_id)
            return
        self.start_heartbeat(
            component=f"Scanner:{account_id}",
            interval=15.0,
            account_id=account_id,
            version=ENGINE_VERSION,
        )
        task = asyncio.create_task(self._scan_loop(account_id))
        self._tasks[account_id] = task

    async def stop_scanning(self, account_id: str) -> None:
        await self.stop_heartbeat()
        task = self._tasks.pop(account_id, None)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        runtime = self._runtimes.pop(account_id, None)
        if runtime:
            try:
                await runtime.disconnect()
            except Exception:
                pass

    async def start_all(self) -> None:
        self._running = True
        async with async_session_factory() as session:
            from sqlalchemy import select
            from database.models import TradingAccount
            stmt = select(TradingAccount).where(TradingAccount.active == True)
            result = await session.execute(stmt)
            accounts = list(result.scalars().all())
        for acc in accounts:
            await self.start_scanning(acc.id)

    async def stop_all(self) -> None:
        self._running = False
        ids = list(self._tasks.keys())
        if ids:
            await asyncio.gather(
                *(self.stop_scanning(aid) for aid in ids),
                return_exceptions=True,
            )

    def is_scanning(self, account_id: str) -> bool:
        return account_id in self._tasks and not self._tasks[account_id].done()


account_scanner = AccountScanner()

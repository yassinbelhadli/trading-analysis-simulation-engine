from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Any

from sqlalchemy.ext.asyncio import AsyncSession

from database.db import async_session_factory
from core_engine.account_manager import AccountManager
from core_engine.events.event_bus import event_bus
from core_engine.events.event_types import EventType


class EngineState(str, Enum):
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    ERROR = "ERROR"
    DISABLED = "DISABLED"


@dataclass
class EngineInstance:
    account_id: str
    state: EngineState = EngineState.STOPPED
    started_at: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None
    error: Optional[str] = None
    task: Optional[asyncio.Task] = None


@dataclass
class EngineStatus:
    account_id: str
    state: str
    started_at: Optional[str]
    last_heartbeat: Optional[str]
    uptime_seconds: float
    error: Optional[str]


class EngineManager:
    def __init__(self):
        self._engines: Dict[str, EngineInstance] = {}

    def _get(self, account_id: str) -> EngineInstance:
        if account_id not in self._engines:
            self._engines[account_id] = EngineInstance(account_id=account_id)
        return self._engines[account_id]

    async def start(self, account_id: str) -> EngineInstance:
        engine = self._get(account_id)
        if engine.state in (EngineState.RUNNING, EngineState.STARTING):
            return engine

        engine.state = EngineState.STARTING
        engine.error = None

        async with async_session_factory() as session:
            mgr = AccountManager(session)
            await mgr.update_engine_status(account_id, "ACTIVE")
            await session.commit()

        engine.state = EngineState.RUNNING
        engine.started_at = datetime.now(timezone.utc)
        engine.last_heartbeat = engine.started_at

        event_bus.publish(EventType.ENGINE_STARTED.value, {
            "event_type": EventType.ENGINE_STARTED.value,
            "account_id": account_id,
            "user_id": None,
            "message": f"Engine started for account {account_id}",
        })
        return engine

    async def stop(self, account_id: str) -> EngineInstance:
        engine = self._get(account_id)
        if engine.task and not engine.task.done():
            engine.task.cancel()
        engine.state = EngineState.STOPPED
        engine.task = None

        async with async_session_factory() as session:
            mgr = AccountManager(session)
            await mgr.update_engine_status(account_id, "STOPPED")
            await session.commit()

        event_bus.publish(EventType.ENGINE_STOPPED.value, {
            "event_type": EventType.ENGINE_STOPPED.value,
            "account_id": account_id,
            "user_id": None,
            "message": f"Engine stopped for account {account_id}",
        })
        return engine

    async def pause(self, account_id: str) -> EngineInstance:
        engine = self._get(account_id)
        old_state = engine.state
        engine.state = EngineState.PAUSED

        if old_state == EngineState.RUNNING:
            async with async_session_factory() as session:
                mgr = AccountManager(session)
                await mgr.update_engine_status(account_id, "PAUSED")
                await session.commit()

        event_bus.publish(EventType.ENGINE_PAUSED.value, {
            "event_type": EventType.ENGINE_PAUSED.value,
            "account_id": account_id,
            "user_id": None,
            "message": f"Engine paused for account {account_id}",
        })
        return engine

    async def resume(self, account_id: str) -> EngineInstance:
        engine = self._get(account_id)
        if engine.state != EngineState.PAUSED:
            return engine
        return await self.start(account_id)

    async def restart(self, account_id: str) -> EngineInstance:
        await self.stop(account_id)
        await asyncio.sleep(0.5)
        return await self.start(account_id)

    async def disable(self, account_id: str) -> EngineInstance:
        engine = self._get(account_id)
        if engine.task and not engine.task.done():
            engine.task.cancel()
        engine.state = EngineState.DISABLED
        engine.task = None

        async with async_session_factory() as session:
            mgr = AccountManager(session)
            await mgr.update_engine_status(account_id, "DISABLED")
            await session.commit()
        return engine

    def heartbeat(self, account_id: str) -> None:
        engine = self._get(account_id)
        if engine.state == EngineState.RUNNING:
            engine.last_heartbeat = datetime.now(timezone.utc)

    def set_error(self, account_id: str, error: str) -> EngineInstance:
        engine = self._get(account_id)
        engine.state = EngineState.ERROR
        engine.error = error

        event_bus.publish(EventType.ENGINE_ERROR.value, {
            "event_type": EventType.ENGINE_ERROR.value,
            "account_id": account_id,
            "user_id": None,
            "message": error,
        })
        return engine

    def get_status(self, account_id: str) -> EngineStatus:
        engine = self._get(account_id)
        now = datetime.now(timezone.utc)
        uptime = 0.0
        if engine.state == EngineState.RUNNING and engine.started_at:
            uptime = (now - engine.started_at).total_seconds()
        return EngineStatus(
            account_id=account_id,
            state=engine.state.value,
            started_at=engine.started_at.isoformat() if engine.started_at else None,
            last_heartbeat=engine.last_heartbeat.isoformat() if engine.last_heartbeat else None,
            uptime_seconds=uptime,
            error=engine.error,
        )

    def list_statuses(self) -> List[EngineStatus]:
        return [self.get_status(aid) for aid in self._engines]

    def is_running(self, account_id: str) -> bool:
        engine = self._engines.get(account_id)
        return engine is not None and engine.state == EngineState.RUNNING


engine_manager = EngineManager()

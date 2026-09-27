from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from database.db import async_session_factory
from database.repositories.account_repository import AccountRepository
from database.repositories.audit_repository import AuditRepository
from core_engine.engine_manager import engine_manager, EngineState

admin_accounts_router = APIRouter()


class UpdateAccountRequest(BaseModel):
    real_trading_enabled: Optional[bool] = None
    broker: Optional[str] = None
    server: Optional[str] = None
    login: Optional[str] = None


@admin_accounts_router.get("/accounts")
async def list_accounts(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    active: Optional[bool] = None,
    verified: Optional[bool] = None,
    engine_status: Optional[str] = None,
):
    async with async_session_factory() as session:
        from sqlalchemy import select
        from database.models import TradingAccount
        stmt = select(TradingAccount).order_by(TradingAccount.created_at.desc()).limit(limit).offset(offset)
        if active is not None:
            stmt = stmt.where(TradingAccount.active == active)
        if verified is not None:
            stmt = stmt.where(TradingAccount.verified == verified)
        if engine_status:
            stmt = stmt.where(TradingAccount.engine_status == engine_status)
        result = await session.execute(stmt)
        accounts = list(result.scalars().all())
        return [
            {
                "id": a.id,
                "user_id": a.user_id,
                "account_type": a.account_type,
                "broker": a.broker,
                "prop_firm": a.prop_firm,
                "platform": a.platform,
                "server": a.server,
                "login": a.login,
                "account_size": a.account_size,
                "balance_snapshot": a.balance_snapshot,
                "equity_snapshot": a.equity_snapshot,
                "demo_real": a.demo_real,
                "engine_status": a.engine_status,
                "verified": a.verified,
                "active": a.active,
                "real_trading_enabled": a.real_trading_enabled,
                "created_at": a.created_at.isoformat(),
            }
            for a in accounts
        ]


@admin_accounts_router.get("/accounts/{account_id}")
async def get_account(account_id: str):
    async with async_session_factory() as session:
        repo = AccountRepository(session)
        account = await repo.get_by_id(account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        eng = engine_manager.get_status(account_id)

        audit_repo = AuditRepository(session)
        audit_logs = await audit_repo.get_by_account(account_id, limit=50)

        return {
            "id": account.id,
            "user_id": account.user_id,
            "account_type": account.account_type,
            "broker": account.broker,
            "prop_firm": account.prop_firm,
            "program": account.program,
            "platform": account.platform,
            "server": account.server,
            "login": account.login,
            "account_size": account.account_size,
            "demo_real": account.demo_real,
            "currency": account.currency,
            "leverage": account.leverage,
            "balance_snapshot": account.balance_snapshot,
            "equity_snapshot": account.equity_snapshot,
            "engine_status": account.engine_status,
            "verified": account.verified,
            "active": account.active,
            "real_trading_enabled": account.real_trading_enabled,
            "created_at": account.created_at.isoformat(),
            "engine": {
                "state": eng.state,
                "uptime_seconds": round(eng.uptime_seconds, 1),
                "error": eng.error,
                "last_heartbeat": eng.last_heartbeat,
            },
            "audit_logs": [
                {
                    "id": log.id,
                    "event_type": log.event_type,
                    "severity": log.severity,
                    "message": log.message[:300],
                    "created_at": log.created_at.isoformat(),
                }
                for log in audit_logs
            ],
        }


@admin_accounts_router.patch("/accounts/{account_id}")
async def update_account(account_id: str, body: UpdateAccountRequest):
    async with async_session_factory() as session:
        repo = AccountRepository(session)
        account = await repo.get_by_id(account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        if body.real_trading_enabled is not None:
            account.real_trading_enabled = body.real_trading_enabled
        if body.broker is not None:
            account.broker = body.broker
        if body.server is not None:
            account.server = body.server
        if body.login is not None:
            account.login = body.login

        await session.commit()
        return {"status": "updated", "account_id": account_id}


@admin_accounts_router.post("/accounts/{account_id}/pause")
async def pause_account(account_id: str):
    async with async_session_factory() as session:
        repo = AccountRepository(session)
        account = await repo.get_by_id(account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        account.active = False
        await session.commit()

    await engine_manager.pause(account_id)
    return {"status": "paused", "account_id": account_id}


@admin_accounts_router.post("/accounts/{account_id}/resume")
async def resume_account(account_id: str):
    async with async_session_factory() as session:
        repo = AccountRepository(session)
        account = await repo.get_by_id(account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        account.active = True
        await session.commit()

    await engine_manager.resume(account_id)
    return {"status": "resumed", "account_id": account_id}


@admin_accounts_router.post("/accounts/{account_id}/disable")
async def disable_account(account_id: str):
    await engine_manager.disable(account_id)
    return {"status": "disabled", "account_id": account_id}


@admin_accounts_router.post("/accounts/{account_id}/remove")
async def remove_account(account_id: str):
    engine_instance = engine_manager._get(account_id)
    engine_instance.state = EngineState.STOPPED
    if engine_instance.task and not engine_instance.task.done():
        engine_instance.task.cancel()
    engine_instance.task = None

    async with async_session_factory() as session:
        from sqlalchemy import delete
        from database.repositories.account_repository import AccountRepository
        from database.repositories.audit_repository import AuditRepository
        from database.models import TradingAccount, RiskProfile, AccountScan, PaperTrade, AuditLog

        repo = AccountRepository(session)
        account = await repo.get_by_id(account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        login = account.login
        server = account.server
        user_id = account.user_id

        audit_repo = AuditRepository(session)
        await audit_repo.add(AuditLog(
            event_type="ACCOUNT_REMOVED",
            severity="warning",
            source="admin_panel",
            message=f"Admin deleted account {account_id} ({login} @ {server})",
            account_id=account_id,
            user_id=user_id,
        ))
        await session.flush()

        await session.execute(delete(RiskProfile).where(RiskProfile.account_id == account_id))
        await session.execute(delete(AccountScan).where(AccountScan.account_id == account_id))
        await session.execute(delete(PaperTrade).where(PaperTrade.account_id == account_id))
        await session.execute(delete(TradingAccount).where(TradingAccount.id == account_id))
        await session.commit()

    return {"status": "deleted", "account_id": account_id}

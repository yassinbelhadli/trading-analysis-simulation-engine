"""Admin MT5 account management (JWT + permission-based).

Mirrors the legacy static-token /admin/accounts endpoints but authenticates
through the same JWT + require_permission model as the rest of the new admin
API (/api/admin/...), so the admin dashboard can manage client trading
accounts without a separate legacy token.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import get_session
from database.models import TradingAccount, User
from security.auth import Permission, require_permission

router = APIRouter(tags=["admin", "accounts"])


class UpdateAccountRequest(BaseModel):
    real_trading_enabled: Optional[bool] = None
    broker: Optional[str] = None
    server: Optional[str] = None
    login: Optional[str] = None


def _account_to_dict(a: TradingAccount, user_email: str | None = None) -> dict:
    return {
        "id": a.id,
        "user_id": a.user_id,
        "user_email": user_email,
        "account_type": a.account_type,
        "broker": a.broker,
        "prop_firm": a.prop_firm,
        "program": a.program,
        "platform": a.platform,
        "server": a.server,
        "login": a.login,
        "name": a.name,
        "account_size": a.account_size,
        "balance_snapshot": a.balance_snapshot,
        "equity_snapshot": a.equity_snapshot,
        "demo_real": a.demo_real,
        "currency": a.currency,
        "leverage": a.leverage,
        "engine_status": a.engine_status,
        "verified": a.verified,
        "active": a.active,
        "real_trading_enabled": a.real_trading_enabled,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


async def _get_account_or_404(session: AsyncSession, account_id: str) -> TradingAccount:
    result = await session.execute(select(TradingAccount).where(TradingAccount.id == account_id))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@router.get("/accounts")
async def list_accounts(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    active: Optional[bool] = None,
    verified: Optional[bool] = None,
    engine_status: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission(Permission.ACCOUNTS_READ)),
):
    """List all client trading accounts with owner email."""
    stmt = (
        select(TradingAccount)
        .order_by(TradingAccount.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if active is not None:
        stmt = stmt.where(TradingAccount.active == active)
    if verified is not None:
        stmt = stmt.where(TradingAccount.verified == verified)
    if engine_status:
        stmt = stmt.where(TradingAccount.engine_status == engine_status)

    result = await session.execute(stmt)
    accounts = list(result.scalars().all())

    # Batch-load owner emails
    user_ids = {a.user_id for a in accounts}
    emails: dict[str, str | None] = {}
    if user_ids:
        ures = await session.execute(select(User.id, User.email).where(User.id.in_(user_ids)))
        emails = {uid: email for uid, email in ures.all()}

    return {
        "items": [_account_to_dict(a, emails.get(a.user_id)) for a in accounts],
        "total": len(accounts),
    }


@router.get("/accounts/{account_id}")
async def get_account(
    account_id: str,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission(Permission.ACCOUNTS_READ)),
):
    """Get a single account with owner email."""
    account = await _get_account_or_404(session, account_id)
    ures = await session.execute(select(User.email).where(User.id == account.user_id))
    email = ures.scalar_one_or_none()
    return _account_to_dict(account, email)


@router.patch("/accounts/{account_id}")
async def update_account(
    account_id: str,
    body: UpdateAccountRequest,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission(Permission.ACCOUNTS_UPDATE)),
):
    """Partially update an account (real-trading toggle, broker, server, login)."""
    account = await _get_account_or_404(session, account_id)
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


@router.post("/accounts/{account_id}/pause")
async def pause_account(
    account_id: str,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission(Permission.ACCOUNTS_UPDATE)),
):
    """Pause an account (deactivate + stop engine)."""
    account = await _get_account_or_404(session, account_id)
    account.active = False
    await session.commit()
    try:
        from core_engine.engine_manager import engine_manager
        await engine_manager.pause(account_id)
    except Exception:
        pass
    return {"status": "paused", "account_id": account_id}


@router.post("/accounts/{account_id}/resume")
async def resume_account(
    account_id: str,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission(Permission.ACCOUNTS_UPDATE)),
):
    """Resume an account (activate + start engine)."""
    account = await _get_account_or_404(session, account_id)
    account.active = True
    await session.commit()
    try:
        from core_engine.engine_manager import engine_manager
        await engine_manager.resume(account_id)
    except Exception:
        pass
    return {"status": "resumed", "account_id": account_id}


@router.post("/accounts/{account_id}/disable")
async def disable_account(
    account_id: str,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission(Permission.ACCOUNTS_UPDATE)),
):
    """Disable the engine for an account (keeps the account record)."""
    await _get_account_or_404(session, account_id)
    try:
        from core_engine.engine_manager import engine_manager
        await engine_manager.disable(account_id)
    except Exception:
        pass
    return {"status": "disabled", "account_id": account_id}

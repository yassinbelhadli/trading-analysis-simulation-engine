"""HTTP adapters for client MT5 account management."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.client_account_service import (
    AccountAlreadyLinkedError,
    AccountConnectionError,
    AccountCredentialsError,
    AccountInputError,
    AccountLimitReachedError,
    AccountLinkedToAnotherUserError,
    AccountNoActiveLicenseError,
    ClientAccountNotFoundError,
    ClientAccountService,
)
from database.db import get_session
from database.repositories import AccountRepository
from security.auth import get_current_user
from core_engine.risk_manager import RiskManager

router = APIRouter(prefix="/client/accounts", tags=["client-accounts"])


@router.get("")
async def client_accounts(
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """List the user's MT5 accounts plus plan usage limits."""
    return await ClientAccountService(session).list_accounts(current_user.id)


@router.post("")
async def add_client_account(
    body: dict,
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Add and verify a new MT5 account."""
    try:
        return await ClientAccountService(session).add_account(current_user.id, body)
    except AccountInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AccountNoActiveLicenseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AccountLimitReachedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (AccountAlreadyLinkedError, AccountLinkedToAnotherUserError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except AccountConnectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/{account_id}")
async def rename_client_account(
    account_id: str,
    body: dict,
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Rename an account (display label only)."""
    try:
        return await ClientAccountService(session).rename_account(current_user.id, account_id, body)
    except ClientAccountNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AccountInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{account_id}")
async def delete_client_account(
    account_id: str,
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Soft-delete an account (stops engine and removes credentials)."""
    try:
        return await ClientAccountService(session).remove_account(current_user.id, account_id)
    except ClientAccountNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{account_id}/disconnect")
async def disconnect_client_account(
    account_id: str,
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Disconnect an account (stop engine -> engine_status STOPPED)."""
    try:
        return await ClientAccountService(session).disconnect_account(current_user.id, account_id)
    except ClientAccountNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{account_id}/reconnect")
async def reconnect_client_account(
    account_id: str,
    body: dict,
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Reconnect an account: re-verify credentials and refresh the snapshot."""
    try:
        return await ClientAccountService(session).reconnect_account(current_user.id, account_id, body)
    except ClientAccountNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (AccountCredentialsError, AccountConnectionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{account_id}/risk-check")
async def risk_check(
    account_id: str,
    body: dict,
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Run the full risk check (daily loss, max loss, drawdown, profit target, funded rules)."""
    repo = AccountRepository(session)
    account = await repo.get_by_id(account_id)
    if not account or account.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Account not found")
    if not account.active:
        raise HTTPException(status_code=400, detail="Account is not active")

    current_equity = float(body.get("current_equity", account.equity_snapshot or 0))
    daily_start_equity = float(body.get("daily_start_equity", current_equity))
    start_balance = float(body.get("start_balance", account.balance_snapshot or 0))

    rm = RiskManager(session)

    daily = await rm.check_daily_loss(account_id, current_equity, daily_start_equity)
    maxl = await rm.check_max_loss(account_id, current_equity, start_balance)
    dd = await rm.check_drawdown(account_id, current_equity, start_balance)

    breaches = []
    if not daily.allowed:
        breaches.append({"type": "DAILY_LOSS", "allowed": False, "reason": daily.reason})
    if not maxl.allowed:
        breaches.append({"type": "MAX_LOSS", "allowed": False, "reason": maxl.reason})
    if not dd.allowed:
        breaches.append({"type": "DRAWDOWN", "allowed": False, "reason": dd.reason})

    profit = None
    min_days = None
    funded_result = None
    if account.account_type == "FUNDED":
        profit = await rm.check_profit_target(account_id, current_equity, start_balance)
        min_days = await rm.check_min_trading_days(account_id)
        funded_result = await rm.evaluate_funded_risk(account_id, current_equity, daily_start_equity, start_balance)
        if not profit.allowed:
            breaches.append({"type": "PROFIT_TARGET", "allowed": False, "reason": profit.reason})
        if not funded_result.allowed:
            breaches.append({"type": "FUNDED_RULE", "allowed": False, "reason": funded_result.reason})

    allowed = len(breaches) == 0
    return {
        "allowed": allowed,
        "breaches": breaches,
        "profit_target": profit.to_dict() if profit else None,
        "min_trading_days": min_days.to_dict() if min_days else None,
        "funded_risk": funded_result.to_dict() if funded_result else None,
    }


@router.post("/{account_id}/record-trading-day")
async def record_trading_day(
    account_id: str,
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Record today as a trading day for minimum trading days tracking."""
    repo = AccountRepository(session)
    account = await repo.get_by_id(account_id)
    if not account or account.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Account not found")

    rm = RiskManager(session)
    await rm.record_trading_day(account_id)
    await session.commit()

    return {"status": "ok", "message": "Trading day recorded."}

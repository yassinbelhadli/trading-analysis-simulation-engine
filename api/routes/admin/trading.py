from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from analytics.analytics_service import AnalyticsService
from api.services.admin_health_service import admin_health_service
from api.services.screenshot_sign import sign_screenshot_url
from core_engine.engine_manager import engine_manager
from database.db import get_session
from database.models import PaperTrade, RiskProfile, TradingAccount
from security.auth import log_event, require_role

BASE_DIR = Path(__file__).resolve().parents[2]
ENGINE_LOG = BASE_DIR / "logs" / "engine.log"

router = APIRouter(tags=["admin", "trading"])

analytics_service = AnalyticsService()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def _serialize_trade(t: PaperTrade) -> dict:
    return {
        "id": t.id,
        "account_id": t.account_id,
        "user_id": t.user_id,
        "symbol": t.symbol,
        "direction": t.direction,
        "entry_price": t.entry_price,
        "current_price": t.entry_price,
        "stop_loss": t.stop_loss,
        "take_profit": t.take_profit,
        "risk_reward": t.risk_reward,
        "lot_size": t.lot_size,
        "risk_percent": t.risk_percent,
        "score": t.score,
        "confidence": t.confidence,
        "rank": t.rank,
        "status": t.status,
        "reasons": t.reasons,
        "session": t.session,
        "market_regime": t.market_regime,
        "candidate_id": t.candidate_id,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "executed_at": t.executed_at.isoformat() if t.executed_at else None,
        "exit_price": t.exit_price,
        "close_reason": t.close_reason,
        "closed_at": t.closed_at.isoformat() if t.closed_at else None,
        "realized_r": t.realized_r,
        "initial_risk_usd": t.initial_risk_usd,
        "mfe": t.mfe,
        "mae": t.mae,
        "breakeven_activated": t.breakeven_activated,
        "partial_closed": t.partial_closed,
        "trade_duration_sec": t.trade_duration_sec,
    }


# ---------------------------------------------------------------------------
# 1. Live Trading Overview
# ---------------------------------------------------------------------------
@router.get("/trading/overview")
async def trading_overview(
    session: AsyncSession = Depends(get_session),
    _=Depends(require_role("owner")),
):
    # Active / filled trades
    active_result = await session.execute(
        select(PaperTrade).where(PaperTrade.status.in_(["PLANNED", "FILLED"])).order_by(PaperTrade.created_at.desc())
    )
    active_trades = active_result.scalars().all()

    # Closed trades (last 24h for daily P&L)
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    daily_result = await session.execute(
        select(PaperTrade).where(
            PaperTrade.status == "CLOSED",
            PaperTrade.closed_at >= since,
        )
    )
    daily_closed = daily_result.scalars().all()

    # All closed trades (for cumulative stats)
    closed_result = await session.execute(
        select(PaperTrade).where(PaperTrade.status == "CLOSED")
    )
    all_closed = closed_result.scalars().all()

    # P&L calculations
    active_pnl = sum(
        ((getattr(t, 'current_price', t.entry_price) or 0) - (t.entry_price or 0)) * (t.lot_size or 0) * (1 if t.direction == "BUY" else -1)
        for t in active_trades if t.status == "FILLED"
    )

    daily_pnl = sum(t.realized_r or 0 for t in daily_closed)
    daily_loss = sum(t.realized_r or 0 for t in daily_closed if (t.realized_r or 0) < 0)

    net_pnl = sum(t.realized_r or 0 for t in all_closed)
    wins = [t for t in all_closed if (t.realized_r or 0) > 0]
    losses = [t for t in all_closed if (t.realized_r or 0) <= 0]
    win_count = len(wins)
    loss_count = len(losses)
    total_closed = len(all_closed)
    win_rate = (win_count / total_closed * 100) if total_closed else 0
    gross_profit = sum(t.realized_r or 0 for t in wins)
    gross_loss = abs(sum(t.realized_r or 0 for t in losses)) or 1
    profit_factor = gross_profit / gross_loss if gross_loss else 0

    # Drawdown (simple — from all closed trades)
    peak = 0.0
    max_dd = 0.0
    running = 0.0
    for t in sorted(all_closed, key=lambda x: x.closed_at or x.created_at or datetime.min.replace(tzinfo=timezone.utc)):
        running += t.realized_r or 0
        if running > peak:
            peak = running
        dd = peak - running
        if dd > max_dd:
            max_dd = dd

    # Accounts / Engine summary
    acc_result = await session.execute(
        select(func.count()).select_from(TradingAccount).where(TradingAccount.active == True)
    )
    connected_accounts = acc_result.scalar() or 0

    counts_result = await session.execute(
        select(func.count()).select_from(PaperTrade).where(PaperTrade.status == "PLANNED")
    )
    pending_orders = counts_result.scalar() or 0

    engine_data = admin_health_service.get_overview_engine()

    return {
        "active_trades": len([t for t in active_trades if t.status == "FILLED"]),
        "pending_orders": pending_orders,
        "floating_pnl": round(active_pnl, 2),
        "daily_pnl": round(daily_pnl, 2),
        "daily_loss": round(daily_loss, 2),
        "net_pnl": round(net_pnl, 2),
        "win_rate": round(win_rate, 1),
        "profit_factor": round(profit_factor, 2),
        "total_trades": total_closed,
        "win_count": win_count,
        "loss_count": loss_count,
        "max_drawdown": round(max_dd, 2),
        "current_drawdown": round(peak - running, 2),
        "connected_accounts": connected_accounts,
        "engine_status": engine_data.get("status", "UNKNOWN"),
        "mt5_connected": engine_data.get("mt5_connected", False),
        "telegram_connected": engine_data.get("telegram_connected", False),
    }


# ---------------------------------------------------------------------------
# 2. Active Trades
# ---------------------------------------------------------------------------
@router.get("/trading/active-trades")
async def active_trades(
    account_id: str = None,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_role("owner")),
):
    query = select(PaperTrade).where(PaperTrade.status.in_(["PLANNED", "FILLED"]))
    if account_id:
        query = query.where(PaperTrade.account_id == account_id)
    query = query.order_by(PaperTrade.created_at.desc())

    result = await session.execute(query)
    trades = result.scalars().all()
    return {"items": [_serialize_trade(t) for t in trades], "total": len(trades)}


# ---------------------------------------------------------------------------
# 3. Trade History
# ---------------------------------------------------------------------------
@router.get("/trading/history")
async def trade_history(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    symbol: str = None,
    direction: str = None,
    close_reason: str = None,
    date_from: str = None,
    date_to: str = None,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_role("owner")),
):
    query = select(PaperTrade).where(PaperTrade.status == "CLOSED")
    count_query = select(func.count()).select_from(PaperTrade).where(PaperTrade.status == "CLOSED")

    if symbol:
        query = query.where(PaperTrade.symbol == symbol.upper())
        count_query = count_query.where(PaperTrade.symbol == symbol.upper())
    if direction:
        query = query.where(PaperTrade.direction == direction.upper())
        count_query = count_query.where(PaperTrade.direction == direction.upper())
    if close_reason:
        query = query.where(PaperTrade.close_reason == close_reason.upper())
        count_query = count_query.where(PaperTrade.close_reason == close_reason.upper())
    if date_from:
        query = query.where(PaperTrade.closed_at >= date_from)
        count_query = count_query.where(PaperTrade.closed_at >= date_from)
    if date_to:
        query = query.where(PaperTrade.closed_at <= date_to)
        count_query = count_query.where(PaperTrade.closed_at <= date_to)

    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(PaperTrade.closed_at.desc()).offset(offset).limit(limit)
    result = await session.execute(query)
    trades = result.scalars().all()

    return {"items": [_serialize_trade(t) for t in trades], "total": total, "limit": limit, "offset": offset}


# ---------------------------------------------------------------------------
# 4. Signals & ICT Setups
# ---------------------------------------------------------------------------
@router.get("/trading/signals")
async def trading_signals(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    _=Depends(require_role("owner")),
):
    query = select(PaperTrade).where(PaperTrade.status == "PLANNED")
    count_query = select(func.count()).select_from(PaperTrade).where(PaperTrade.status == "PLANNED")

    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(PaperTrade.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(query)
    trades = result.scalars().all()

    return {"items": [_serialize_trade(t) for t in trades], "total": total, "limit": limit, "offset": offset}


# ---------------------------------------------------------------------------
# 5. Risk Monitor
# ---------------------------------------------------------------------------
@router.get("/trading/risk")
async def risk_monitor(
    session: AsyncSession = Depends(get_session),
    _=Depends(require_role("owner")),
):
    profiles_result = await session.execute(
        select(RiskProfile).options(selectinload(RiskProfile.account)).order_by(RiskProfile.last_risk_update.desc().nullslast())
    )
    profiles = profiles_result.scalars().all()

    total_daily_loss = 0
    total_max_loss = 0
    total_drawdown = 0
    active_risk = 0
    breached = 0
    items = []

    for rp in profiles:
        daily_loss_pct = rp.current_daily_loss_pct or 0
        max_loss_pct = rp.current_max_loss_pct or 0
        dd = 0
        if rp.day_start_equity and rp.daily_high_equity and rp.day_start_equity > 0:
            dd = ((rp.daily_high_equity - rp.day_start_equity) / rp.day_start_equity) * 100

        total_daily_loss += abs(daily_loss_pct)
        total_max_loss += abs(max_loss_pct)
        total_drawdown += abs(dd)

        items.append({
            "account_id": rp.account_id,
            "login": rp.account.login if rp.account else None,
            "daily_loss_limit": rp.daily_loss,
            "current_daily_loss_pct": round(daily_loss_pct, 2),
            "max_loss_limit": rp.max_loss,
            "current_max_loss_pct": round(max_loss_pct, 2),
            "profit_target": rp.profit_target,
            "max_risk_per_trade": rp.max_risk_trade,
            "day_start_balance": rp.day_start_balance,
            "day_start_equity": rp.day_start_equity,
            "daily_drawdown_pct": round(dd, 2),
            "breached": daily_loss_pct <= -100 or max_loss_pct <= -100,
        })
        if daily_loss_pct <= -100 or max_loss_pct <= -100:
            breached += 1

    # Active risk from open trades
    active_result = await session.execute(
        select(func.sum(PaperTrade.initial_risk_usd)).where(PaperTrade.status == "FILLED")
    )
    active_risk = active_result.scalar() or 0

    return {
        "items": items,
        "total_accounts": len(profiles),
        "breached_accounts": breached,
        "total_daily_loss_pct": round(total_daily_loss, 2),
        "total_max_loss_pct": round(total_max_loss, 2),
        "total_drawdown_pct": round(abs(total_drawdown), 2),
        "active_risk_usd": round(float(active_risk), 2),
    }


# ---------------------------------------------------------------------------
# 6. Performance
# ---------------------------------------------------------------------------
@router.get("/trading/performance")
async def trading_performance(
    session: AsyncSession = Depends(get_session),
    _=Depends(require_role("owner")),
):
    report = await analytics_service.compute_full_report()
    return report


# ---------------------------------------------------------------------------
# 7. Engine Monitor
# ---------------------------------------------------------------------------
@router.get("/trading/engine")
async def engine_monitor(
    session: AsyncSession = Depends(get_session),
    _=Depends(require_role("owner")),
):
    health = admin_health_service.get_health_json()
    engines = admin_health_service.get_engines()
    heartbeat = admin_health_service.get_heartbeat()
    report = admin_health_service.get_health_report()

    cycle_counts = {}
    for e in engines:
        if e.get("state") == "RUNNING":
            cycle_counts["running"] = cycle_counts.get("running", 0) + 1
        elif e.get("state") == "STOPPED":
            cycle_counts["stopped"] = cycle_counts.get("stopped", 0) + 1
        else:
            cycle_counts["other"] = cycle_counts.get("other", 0) + 1

    return {
        "system_version": health.get("system_version"),
        "uptime_seconds": report.get("uptime_seconds") or health.get("uptime_seconds"),
        "pid": heartbeat.get("pid"),
        "instance_id": heartbeat.get("instance_id"),
        "cycles": report.get("cycles") or heartbeat.get("cycles"),
        "memory_mb": report.get("memory_mb"),
        "cpu_percent": report.get("cpu_percent"),
        "mt5_connected": report.get("mt5_connected", False) or heartbeat.get("mt5_connected", False),
        "telegram_connected": report.get("telegram_connected", False),
        "heartbeat_age_sec": report.get("heartbeat_age_sec"),
        "active_trades": report.get("active_trades", 0),
        "engine_counts": cycle_counts,
        "components": health.get("components"),
    }


# ---------------------------------------------------------------------------
# 8. Engine Logs
# ---------------------------------------------------------------------------
@router.get("/trading/engine/logs")
async def engine_logs(
    limit: int = Query(100, le=500),
    _=Depends(require_role("owner")),
):
    logs: list[dict] = []
    try:
        if ENGINE_LOG.exists():
            with open(str(ENGINE_LOG), encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            for line in lines[-limit:]:
                parts = line.strip().split(" | ", 2)
                if len(parts) == 3:
                    logs.append({"timestamp": parts[0], "level": parts[1], "message": parts[2]})
                elif len(parts) == 2:
                    logs.append({"timestamp": parts[0], "level": "INFO", "message": parts[1]})
                else:
                    logs.append({"timestamp": "", "level": "INFO", "message": line.strip()})
    except Exception:
        pass
    return {"items": logs, "total": len(logs)}


# ---------------------------------------------------------------------------
# Trading Controls
# ---------------------------------------------------------------------------
@router.post("/trading/control/enable")
async def control_enable(
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_role("owner")),
):
    result = await session.execute(select(TradingAccount).where(TradingAccount.active == True))
    accounts = result.scalars().all()
    for a in accounts:
        a.engine_status = "ACTIVE"
        a.real_trading_enabled = True
    audit_id = await log_event(session, "trading.enable", "Trading enabled for all accounts",
                                user_id=current_user.id)
    await session.commit()
    return {"success": True, "audit_id": audit_id, "message": f"Enabled trading for {len(accounts)} accounts"}


@router.post("/trading/control/disable")
async def control_disable(
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_role("owner")),
):
    result = await session.execute(select(TradingAccount).where(TradingAccount.active == True))
    accounts = result.scalars().all()
    for a in accounts:
        a.engine_status = "DISABLED"
        a.real_trading_enabled = False
    audit_id = await log_event(session, "trading.disable", "Trading disabled for all accounts",
                                user_id=current_user.id)
    await session.commit()
    return {"success": True, "audit_id": audit_id, "message": f"Disabled trading for {len(accounts)} accounts"}


@router.post("/trading/control/pause")
async def control_pause(
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_role("owner")),
):
    for aid in list(engine_manager._engines.keys()):
        await engine_manager.pause(aid)
    audit_id = await log_event(session, "trading.pause", "Trading paused",
                                user_id=current_user.id)
    await session.commit()
    return {"success": True, "audit_id": audit_id, "message": "Trading paused"}


@router.post("/trading/control/resume")
async def control_resume(
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_role("owner")),
):
    for aid in list(engine_manager._engines.keys()):
        await engine_manager.resume(aid)
    audit_id = await log_event(session, "trading.resume", "Trading resumed",
                                user_id=current_user.id)
    await session.commit()
    return {"success": True, "audit_id": audit_id, "message": "Trading resumed"}


@router.post("/trading/control/close-all")
async def control_close_all(
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_role("owner")),
):
    result = await session.execute(select(PaperTrade).where(PaperTrade.status == "FILLED"))
    trades = result.scalars().all()
    now = datetime.now(timezone.utc)
    for t in trades:
        t.status = "CLOSED"
        t.close_reason = "MANUAL_CLOSE_ALL"
        t.closed_at = now
        t.exit_price = t.current_price or t.entry_price
    audit_id = await log_event(session, "trading.close_all", f"Closed {len(trades)} trades",
                                user_id=current_user.id)
    await session.commit()
    return {"success": True, "audit_id": audit_id, "message": f"Closed {len(trades)} trades"}


@router.post("/trading/control/close-symbol")
async def control_close_symbol(
    body: dict,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_role("owner")),
):
    symbol = (body.get("symbol") or "").upper()
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol required")
    result = await session.execute(
        select(PaperTrade).where(PaperTrade.status == "FILLED", PaperTrade.symbol == symbol)
    )
    trades = result.scalars().all()
    now = datetime.now(timezone.utc)
    for t in trades:
        t.status = "CLOSED"
        t.close_reason = "MANUAL_CLOSE_SYMBOL"
        t.closed_at = now
        t.exit_price = t.current_price or t.entry_price
    audit_id = await log_event(session, "trading.close_symbol", f"Closed {len(trades)} {symbol} trades",
                                user_id=current_user.id)
    await session.commit()
    return {"success": True, "audit_id": audit_id, "message": f"Closed {len(trades)} {symbol} trades"}


@router.post("/trading/control/emergency-stop")
async def control_emergency_stop(
    session: AsyncSession = Depends(get_session),
    current_user=Depends(require_role("owner")),
):
    # Stop all engines
    for aid in list(engine_manager._engines.keys()):
        await engine_manager.stop(aid)
    # Disable all accounts
    result = await session.execute(select(TradingAccount).where(TradingAccount.active == True))
    accounts = result.scalars().all()
    for a in accounts:
        a.engine_status = "DISABLED"
        a.real_trading_enabled = False
    # Close all filled trades
    trade_result = await session.execute(select(PaperTrade).where(PaperTrade.status == "FILLED"))
    trades = trade_result.scalars().all()
    now = datetime.now(timezone.utc)
    for t in trades:
        t.status = "CLOSED"
        t.close_reason = "EMERGENCY_STOP"
        t.closed_at = now
        t.exit_price = t.current_price or t.entry_price
    audit_id = await log_event(session, "trading.emergency_stop",
                                f"Emergency stop — {len(trades)} trades closed, {len(accounts)} accounts disabled",
                                user_id=current_user.id)
    await session.commit()
    return {"success": True, "audit_id": audit_id,
            "message": f"Emergency stop — {len(trades)} trades closed, {len(accounts)} accounts disabled"}


# ---------------------------------------------------------------------------
# Trade Snapshot (for Dashboard Replay)
# ---------------------------------------------------------------------------
@router.get("/trade/{trade_id}/snapshot")
@router.get("/trading/trade/{trade_id}/snapshot")
async def get_trade_snapshot(
    trade_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: dict = Depends(require_role("owner")),
):
    result = await session.execute(select(PaperTrade).where(PaperTrade.id == trade_id))
    trade = result.scalar_one_or_none()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")

    screenshots = {}
    ss_dir = Path(__file__).resolve().parents[3] / "storage" / "screenshots" / trade_id
    if ss_dir.exists():
        for f in ss_dir.iterdir():
            if f.suffix in (".png", ".jpg", ".jpeg"):
                screenshots[f.stem] = sign_screenshot_url(trade_id, f.name)

    return {
        "trade": {
            "id": trade.id,
            "symbol": trade.symbol,
            "direction": trade.direction,
            "entry_price": trade.entry_price,
            "stop_loss": trade.stop_loss,
            "take_profit": trade.take_profit,
            "status": trade.status,
            "score": trade.score,
            "confidence": trade.confidence,
            "reasons": trade.reasons.split(",") if trade.reasons else [],
            "session": trade.session,
            "market_regime": trade.market_regime,
            "created_at": trade.created_at.isoformat() if trade.created_at else None,
            "closed_at": trade.closed_at.isoformat() if trade.closed_at else None,
            "exit_price": trade.exit_price,
            "close_reason": trade.close_reason,
            "realized_pnl": trade.realized_pnl,
            "realized_r": trade.realized_r,
            "mfe": trade.mfe,
            "mae": trade.mae,
            "breakeven_activated": trade.breakeven_activated,
            "partial_closed": trade.partial_closed,
        },
        "snapshot": trade.snapshot,
        "screenshots": screenshots,
    }

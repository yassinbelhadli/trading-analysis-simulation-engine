"""
Seed the DEV database (ict_funded_ea) with a persistent Human Validation Kit:
owner / admin / client demo accounts plus realistic-but-synthetic data covering
the frozen backend contracts (license, subscription, MT4/MT5 accounts, scans,
risk profile, signals, closed trades, audit logs, ticket, news, news events).

Usage:
    python -m scripts.seed_demo

Guards
------
- Refuses to run against QA / golden databases (name ends `_qa` / `_golden`).
- Never touches config/.env, production config, DNS, deployment, or external
  services.  No SMTP is used: all demo accounts are email_verified=True with
  2FA disabled, so human validation never depends on email delivery.
- Idempotent and deterministic: every entity uses a fixed UUID (uuid5) or a
  fixed unique key, and existing rows are skipped.  Re-running is safe and
  produces identical counts (verified by scripts/_qa_human_validation.py).

All synthetic data is clearly labelled in docs/human_validation_kit.md.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func, select

from database.models import (
    AccountScan,
    AuditLog,
    EABuild,
    License,
    News,
    NewsEvent,
    PaperTrade,
    PlanDefinition,
    RiskProfile,
    Role,
    SiteSetting,
    Subscription,
    SupportTicket,
    TradingAccount,
    User,
)
from security.access_control import seed_roles_and_permissions
from security.account_fingerprint import build_account_fingerprint
from security.password import hash_password

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

DEMO_OWNER_EMAIL = "demo.owner@ict-ea-demo.dev"
DEMO_ADMIN_EMAIL = "demo.admin@ict-ea-demo.dev"
DEMO_CLIENT_EMAIL = "demo.client@ict-ea-demo.dev"

DEMO_OWNER_PASSWORD = "OwnerDemo!2026"
DEMO_ADMIN_PASSWORD = "AdminDemo!2026"
DEMO_CLIENT_PASSWORD = "ClientDemo!2026"

DEMO_LICENSE_KEY = "ICT-DEMO-A1B2-C3D4"
DEMO_TICKET_NUMBER = "DEMO-2026-0001"
DEMO_EA_VERSION = "9.9.9-demo"

_PLAN = "premium"
_NOW = None


def _uid(*parts: str) -> str:
    """Deterministic UUID for an entity, so re-runs never duplicate rows."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "/".join(("ict-ea-demo", *parts))))


def _dt(days: float = 0.0) -> datetime:
    return _NOW + timedelta(days=days)


def _require_dev_database() -> None:
    url = os.getenv("DATABASE_URL", "")
    lower = url.lower()
    if "_qa" in lower or "_golden" in lower:
        raise SystemExit(
            "Refusing to seed: DATABASE_URL points to a QA/golden database "
            "(name contains '_qa' or '_golden'). Demo seed is for the dev "
            "database only (default: ict_funded_ea)."
        )


# ---------------------------------------------------------------------------
# Demo users
# ---------------------------------------------------------------------------
async def _ensure_users(session) -> dict:
    made = 0
    specs = [
        (DEMO_OWNER_EMAIL, DEMO_OWNER_PASSWORD, "owner", "Demo", "Owner"),
        (DEMO_ADMIN_EMAIL, DEMO_ADMIN_PASSWORD, "admin", "Demo", "Admin"),
        (DEMO_CLIENT_EMAIL, DEMO_CLIENT_PASSWORD, "client", "Demo", "Client"),
    ]
    for email, password, role_name, first, last in specs:
        result = await session.execute(select(User).where(User.email == email))
        if result.scalar_one_or_none() is not None:
            continue
        result = await session.execute(select(Role).where(Role.name == role_name))
        role = result.scalar_one_or_none()
        session.add(
            User(
                id=_uid("user", role_name),
                email=email,
                password_hash=hash_password(password),
                first_name=first,
                last_name=last,
                role_id=role.id if role else None,
                language="EN",
                timezone="UTC",
                country="US",
                status="active",
                account_status="active",
                email_verified=True,          # no SMTP dependency on purpose
                two_factor_enabled=False,     # no 2FA dependency on purpose
            )
        )
        made += 1
    if made:
        await session.flush()
    return {"made": made}


async def _user_id(session, email: str) -> str | None:
    result = await session.execute(select(User.id).where(User.email == email))
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Plans, license, subscription, accounts
# ---------------------------------------------------------------------------
async def _ensure_plans(session) -> int:
    made = 0
    specs = [
        ("premium", "Premium", 99, 990, 10, 10000, 5.0),
        ("professional", "Professional", 59, 590, 3, 3000, 2.0),
    ]
    for pid, name, pm, py, max_acc, max_loss, risk in specs:
        result = await session.execute(select(PlanDefinition).where(PlanDefinition.id == pid))
        if result.scalar_one_or_none() is not None:
            continue
        session.add(
            PlanDefinition(
                id=pid,
                name=name,
                price_monthly=pm,
                price_yearly=py,
                max_accounts=max_acc,
                max_daily_loss=max_loss,
                max_risk_per_trade=risk,
                features={},
                on_sale=False,
                sort_order=1 if pid == "premium" else 2,
            )
        )
        made += 1
    if made:
        await session.flush()
    return made


async def _ensure_client_data(session, client_id: str) -> dict:
    counts = {}

    # License -------------------------------------------------------------
    result = await session.execute(select(License).where(License.license_key == DEMO_LICENSE_KEY))
    license_row = result.scalar_one_or_none()
    if license_row is None:
        license_row = License(
            id=_uid("license", "client"),
            user_id=client_id,
            license_key=DEMO_LICENSE_KEY,
            plan=_PLAN,
            status="active",
            expires_at=_dt(365),
            max_accounts=3,
            bound_at=_dt(0),
            transfer_locked=True,
        )
        session.add(license_row)
        await session.flush()
    counts["licenses"] = 1

    # Subscription --------------------------------------------------------
    result = await session.execute(
        select(Subscription).where(Subscription.user_id == client_id)
    )
    if result.scalar_one_or_none() is None:
        session.add(
            Subscription(
                id=_uid("subscription", "client"),
                user_id=client_id,
                plan=_PLAN,
                billing_cycle="monthly",
                price=99.0,
                start_date=_dt(-20),
                end_date=_dt(10),
                active=True,
            )
        )
    counts["subscriptions"] = 1

    # Trading accounts ----------------------------------------------------
    account_specs = [
        dict(
            entity="account_funded",
            name="Funded Demo MT5",
            platform="MT5",
            server="ICMarkets-Demo01",
            login="88001234",
            account_type="FUNDED",
            prop_firm="DemoProp LLC",
            program="Funded 100K Demo",
            program_type="evaluation",
            broker="DemoProp Broker",
            account_size=100000.0,
            balance_snapshot=100842.55,
            equity_snapshot=100731.20,
            leverage="1:100",
            bind_license=True,
            build=4020,
        ),
        dict(
            entity="account_challenge",
            name="Challenge Demo MT4",
            platform="MT4",
            server="DemoProp-MT4-Demo",
            login="66009876",
            account_type="CHALLENGE",
            prop_firm="DemoProp LLC",
            program="Sprint 50K Demo",
            program_type="evaluation",
            broker="DemoProp Broker",
            account_size=50000.0,
            balance_snapshot=49877.10,
            equity_snapshot=49877.10,
            leverage="1:50",
            bind_license=False,
            build=4120,
        ),
    ]

    accounts = {}
    for spec in account_specs:
        acc_id = _uid("account", spec["entity"])
        result = await session.execute(
            select(TradingAccount).where(TradingAccount.id == acc_id)
        )
        acc = result.scalar_one_or_none()
        if acc is None:
            acc = TradingAccount(
                id=acc_id,
                user_id=client_id,
                name=spec["name"],
                platform=spec["platform"],
                server=spec["server"],
                login=spec["login"],
                account_type=spec["account_type"],
                prop_firm=spec["prop_firm"],
                program=spec["program"],
                program_type=spec["program_type"],
                broker=spec["broker"],
                account_size=spec["account_size"],
                demo_real="demo",
                trade_mode="demo",
                currency="USD",
                leverage=spec["leverage"],
                balance_snapshot=spec["balance_snapshot"],
                equity_snapshot=spec["equity_snapshot"],
                symbol_mapping={"XAUUSD": "XAUUSD", "NAS100": "NAS100", "XRPUSD": "XRPUSD"},
                account_fingerprint=build_account_fingerprint(
                    spec["platform"], spec["server"], spec["login"]
                ),
                license_id=license_row.id if spec["bind_license"] else None,
                engine_status="ACTIVE",
                verified=True,
                active=True,
                real_trading_enabled=False,
            )
            session.add(acc)
            await session.flush()
        accounts[spec["entity"]] = acc

        # Scan (per account) ------------------------------------------------
        scan_id = _uid("scan", spec["entity"])
        result = await session.execute(select(AccountScan).where(AccountScan.id == scan_id))
        if result.scalar_one_or_none() is None:
            session.add(
                AccountScan(
                    id=scan_id,
                    account_id=acc.id,
                    broker_detected=spec["broker"],
                    balance_detected=spec["balance_snapshot"],
                    equity_detected=spec["equity_snapshot"],
                    leverage_detected=spec["leverage"],
                    symbols_detected="XAUUSD,NAS100,XRPUSD,BTCUSD",
                    mismatches="",
                    build=spec["build"],
                    timezone_detected="UTC",
                    scan_status="verified" if spec["bind_license"] else "success",
                    scanned_at=_dt(-1),
                )
            )

    counts["accounts"] = len(accounts)
    counts["scans"] = len(accounts)

    # Risk profile (funded account only) -----------------------------------
    funded = accounts["account_funded"]
    result = await session.execute(
        select(RiskProfile).where(RiskProfile.account_id == funded.id)
    )
    if result.scalar_one_or_none() is None:
        session.add(
            RiskProfile(
                id=_uid("risk", "funded"),
                account_id=funded.id,
                daily_loss=500.0,
                max_loss=2000.0,
                profit_target=8000.0,
                max_risk_trade=0.5,
                mode="balanced",
                initial_balance=100000.0,
                day_start_balance=100842.55,
                day_start_equity=100731.20,
                daily_high_equity=100910.0,
                drawdown_type="static",
                last_risk_update=_dt(0),
            )
        )
    counts["risk_profiles"] = 1

    # Paper trades ----------------------------------------------------------
    planned = [
        # (uid, symbol, direction, entry, sl, tp, lot, risk_pct, score, conf, rank, session, regime, hours_ago, reasons)
        ("signal_1", "XAUUSD", "BUY", 2678.50, 2668.00, 2702.00, 0.10, 0.35, 82, 78, "A+", "asia", "trending", 0.8,
         "Liquidity sweep of Asian low + bullish FVG filled at 2674.2; displacement into order block"),
        ("signal_2", "XRPUSD", "BUY", 0.6240, 0.6190, 0.6340, 5000, 0.30, 76, 71, "B+", "london", "range", 2.0,
         "Equal highs swept + CHoCH on M15; retest of demand zone"),
        ("signal_3", "NAS100", "SELL", 20145.0, 20185.0, 20065.0, 1.0, 0.40, 71, 66, "B", "ny", "trending", 3.5,
         "Bearish order block rejected price; premium delivery back to dealing range"),
        ("signal_4", "BTCUSD", "BUY", 95400.0, 94650.0, 97200.0, 1.0, 0.30, 74, 69, "B+", "asia", "range", 5.0,
         "Weekly FVG + mitigation of sell-side liquidity below prior low"),
        ("signal_5", "EURUSD", "SELL", 1.0842, 1.0872, 1.0782, 1.0, 0.25, 68, 63, "C+", "london", "trending", 26.0,
         "OTE + FVG sweep of buy-side liquidity below prior H4 high"),
    ]
    closed = [
        # (uid, symbol, direction, entry, sl, tp, exit, lot, rr, score, conf, rank, session, regime, closed_hours_ago, close_reason, pnl, mfe, mae)
        ("closed_1", "XAUUSD", "BUY", 2610.50, 2598.00, 2641.00, 2641.00, 0.10, 2.35, 85, 80, "A+", "london", "trending", 3.0, "TP", 305.00, 30.5, -12.5),
        ("closed_2", "EURUSD", "SELL", 1.0850, 1.0880, 1.0820, 1.0820, 1.0, 1.0, 72, 68, "B", "ny", "range", 6.0, "TP", 300.00, 30.0, -30.0),
        ("closed_3", "NAS100", "BUY", 20000.0, 19960.0, 20030.0, 20030.0, 1.0, 0.75, 69, 64, "B", "asia", "trending", 9.0, "TP", 300.00, 32.0, -40.0),
        ("closed_4", "XRPUSD", "BUY", 0.6100, 0.6040, 0.6170, 0.6170, 5000, 1.17, 74, 70, "B+", "london", "range", 28.0, "TP", 350.00, 70.0, -60.0),
        ("closed_5", "BTCUSD", "SELL", 96200.0, 96800.0, 96050.0, 96050.0, 1.0, 0.5, 70, 66, "B", "ny", "trending", 30.0, "TP", 1500.00, 150.0, -600.0),
        ("closed_6", "XAUUSD", "BUY", 2630.00, 2624.00, 2660.00, 2624.00, 1.0, 0.5, 66, 62, "C+", "asia", "range", 26.0, "SL", -600.00, 10.0, -60.0),
    ]

    trade_count = 0
    for uid_key, symbol, direction, entry, sl, tp, lot, risk_pct, score, conf, rank, sess, regime, hours_ago, reasons in planned:
        pid = _uid("signal", uid_key)
        result = await session.execute(select(PaperTrade).where(PaperTrade.id == pid))
        if result.scalar_one_or_none() is not None:
            continue
        session.add(
            PaperTrade(
                id=pid,
                account_id=funded.id,
                user_id=client_id,
                symbol=symbol,
                direction=direction,
                entry_price=entry,
                stop_loss=sl,
                take_profit=tp,
                risk_reward=round(abs(tp - entry) / abs(entry - sl), 2) if sl != entry else 0.0,
                lot_size=lot,
                risk_percent=risk_pct,
                score=score,
                confidence=conf,
                rank=rank,
                status="PLANNED",
                reasons=reasons,
                session=sess,
                market_regime=regime,
                created_at=_dt(-hours_ago / 24),
            )
        )
        trade_count += 1

    open_trade_id = _uid("signal", "open")
    result = await session.execute(select(PaperTrade).where(PaperTrade.id == open_trade_id))
    if result.scalar_one_or_none() is None:
        session.add(
            PaperTrade(
                id=open_trade_id,
                account_id=funded.id,
                user_id=client_id,
                symbol="XAUUSD",
                direction="BUY",
                entry_price=2640.10,
                stop_loss=2625.00,
                take_profit=2670.10,
                risk_reward=2.0,
                lot_size=0.20,
                risk_percent=0.5,
                score=85,
                confidence=80,
                rank="A",
                status="OPEN",
                reasons="Judas swing into FVG; liquidity sweep above prior high mitigated",
                session="london",
                market_regime="trending",
                created_at=_dt(-0.25),
                executed_at=_dt(-0.22),
            )
        )
        trade_count += 1

    for uid_key, symbol, direction, entry, sl, tp, exit_px, lot, rr, score, conf, rank, sess, regime, hours_ago, close_reason, pnl, mfe, mae in closed:
        cid = _uid("closed", uid_key)
        result = await session.execute(select(PaperTrade).where(PaperTrade.id == cid))
        if result.scalar_one_or_none() is not None:
            continue
        executed = _dt(-hours_ago / 24 - 2.0 / 24)
        session.add(
            PaperTrade(
                id=cid,
                account_id=funded.id,
                user_id=client_id,
                symbol=symbol,
                direction=direction,
                entry_price=entry,
                stop_loss=sl,
                take_profit=tp,
                risk_reward=rr,
                lot_size=lot,
                risk_percent=round(rr * 0.5, 2),
                score=score,
                confidence=conf,
                rank=rank,
                status="CLOSED",
                reasons=f"Synthetic closed {symbol} {direction} — {close_reason}",
                session=sess,
                market_regime=regime,
                created_at=executed,
                executed_at=executed,
                exit_price=exit_px,
                close_reason=close_reason,
                realized_pnl=pnl,
                closed_at=_dt(-hours_ago / 24),
                mfe=mfe,
                mae=mae,
                realized_r=round(abs(exit_px - entry) / abs(entry - sl), 2) if sl != entry else 0.0,
                initial_risk_usd=round(lot * abs(entry - sl), 2),
                validation_batch=1,
            )
        )
        trade_count += 1

    counts["paper_trades"] = trade_count
    return counts


# ---------------------------------------------------------------------------
# Audit trail (synthetic, no ERROR within the last 24h)
# ---------------------------------------------------------------------------
async def _ensure_audit(session, users: dict) -> int:
    entries = [
        # (uid, user, account, event, severity, source, message, hours_ago)
        (_uid("audit", "owner_login"), users["owner"], None, "auth.login", "INFO", "web", "User logged in", 2),
        (_uid("audit", "admin_login"), users["admin"], None, "auth.login", "INFO", "web", "User logged in", 2),
        (_uid("audit", "client_login"), users["client"], None, "auth.login", "INFO", "web", "User logged in", 1),
        (_uid("audit", "license_activated"), users["client"], None, "license.activated", "INFO", "web", "Demo license activated (synthetic)", 1),
        (_uid("audit", "account_connected_1"), users["client"], None, "account.connected", "INFO", "web", "MT5 demo account connected (synthetic)", 1),
        (_uid("audit", "account_connected_2"), users["client"], None, "account.connected", "INFO", "web", "MT4 demo account connected (synthetic)", 1),
        (_uid("audit", "trade_opened"), users["client"], None, "trade.opened", "INFO", "engine", "XAUUSD BUY opened (synthetic)", 5),
        (_uid("audit", "trade_closed_1"), users["client"], None, "trade.closed", "INFO", "engine", "XAUUSD BUY closed at TP (synthetic)", 3),
        (_uid("audit", "risk_watch"), users["client"], None, "risk.stop", "WARNING", "engine", "Daily loss limit approaching — trading paused (synthetic demo entry)", 1),
    ]
    made = 0
    for uid, user_id, account_id, event, severity, source, message, hours_ago in entries:
        result = await session.execute(select(AuditLog).where(AuditLog.id == uid))
        if result.scalar_one_or_none() is not None:
            continue
        session.add(
            AuditLog(
                id=uid,
                user_id=user_id,
                account_id=account_id,
                event_type=event,
                severity=severity,
                source=source,
                message=message,
                payload_json={"synthetic": True},
                created_at=_dt(-hours_ago / 24),
            )
        )
        made += 1
    return made


# ---------------------------------------------------------------------------
# Support, news, EA builds, settings marker
# ---------------------------------------------------------------------------
async def _ensure_misc(session, client_id: str) -> dict:
    counts = {}

    result = await session.execute(
        select(SupportTicket).where(SupportTicket.ticket_number == DEMO_TICKET_NUMBER)
    )
    if result.scalar_one_or_none() is None:
        session.add(
            SupportTicket(
                id=_uid("ticket", "client"),
                user_id=client_id,
                ticket_number=DEMO_TICKET_NUMBER,
                subject="Demo: help connecting my MT5 account",
                description="Synthetic demo ticket — please close or reply to test the admin workflow.",
                category="support",
                status="open",
                priority="medium",
                created_at=_dt(-1),
            )
        )
        counts["tickets"] = 1
    else:
        counts["tickets"] = 1

    news_id = _uid("news", "welcome")
    result = await session.execute(select(News).where(News.id == news_id))
    if result.scalar_one_or_none() is None:
        session.add(
            News(
                id=news_id,
                title="Welcome to your demo environment",
                body="Synthetic announcement so the news list is populated. No real action required.",
                category="announcement",
                published=True,
                created_at=_dt(-2),
            )
        )
        counts["news"] = 1
    else:
        counts["news"] = 1

    events = [
        ("DEMO-FF-2026-0701", "USD CPI m/m", "HIGH", 1.2, "13:30"),
        ("DEMO-FF-2026-0702", "USD FOMC Statement", "HIGH", 2.2, "19:00"),
    ]
    made_events = 0
    for news_id_str, event, impact, days, hhmm in events:
        result = await session.execute(
            select(NewsEvent).where(NewsEvent.news_id == news_id_str)
        )
        if result.scalar_one_or_none() is not None:
            made_events += 1
            continue
        when = _dt(days).replace(hour=int(hhmm.split(":")[0]), minute=int(hhmm.split(":")[1]))
        session.add(
            NewsEvent(
                news_id=news_id_str,
                time=when,
                currency="USD",
                event=event,
                impact=impact,
                forecast="0.2%",
                previous="0.1%",
                status="UPCOMING",
            )
        )
        made_events += 1
    counts["news_events"] = made_events

    result = await session.execute(select(EABuild).where(EABuild.version == DEMO_EA_VERSION))
    if result.scalar_one_or_none() is None:
        session.add(
            EABuild(
                id=_uid("ea_build", "demo"),
                version=DEMO_EA_VERSION,
                release_notes="Synthetic demo build — not downloadable.",
                changelog="Demo",
                is_latest=False,
                released_at=_dt(-5),
            )
        )
        counts["ea_builds"] = 1
    else:
        counts["ea_builds"] = 1

    marker_key = "demo.seed_version"
    result = await session.execute(select(SiteSetting).where(SiteSetting.key == marker_key))
    marker = result.scalar_one_or_none()
    if marker is None:
        session.add(
            SiteSetting(
                key=marker_key,
                value={"version": 1, "seeded_at": _NOW.isoformat(timespec="seconds")},
                category="demo",
                updated_at=_NOW,
            )
        )
    else:
        marker.value = {"version": 1, "seeded_at": _NOW.isoformat(timespec="seconds")}
        marker.updated_at = _NOW
    counts["site_settings"] = 1

    return counts


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
async def seed() -> dict:
    """Idempotent seed. Safe to call more than once (same process or repeated
    CLI runs) — returns a summary dict with stable counts.

    Uses its own short-lived engine so repeated in-process calls (QA) never
    share connections across asyncio event loops.
    """
    global _NOW
    _NOW = datetime.now(timezone.utc)

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    engine = create_async_engine(
        os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:cimoro2008@localhost:5432/ict_funded_ea")
    )
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            # Fresh dev databases have no tables yet — create schema first.
            from database.base import Base
            await session.run_sync(lambda c: Base.metadata.create_all(c.bind))

            await seed_roles_and_permissions(session)

            users_made = await _ensure_users(session)
            client_id = await _user_id(session, DEMO_CLIENT_EMAIL)
            owner_id = await _user_id(session, DEMO_OWNER_EMAIL)
            admin_id = await _user_id(session, DEMO_ADMIN_EMAIL)
            plans_made = await _ensure_plans(session)
            client_counts = await _ensure_client_data(session, client_id)
            audit_made = await _ensure_audit(
                session, {"owner": owner_id, "admin": admin_id, "client": client_id}
            )
            misc = await _ensure_misc(session, client_id)

            await session.commit()

            summary = {
                "users_created": users_made["made"],
                "plans_created": plans_made,
                **client_counts,
                "audit_entries_created": audit_made,
                **misc,
                "total_users": await _count(session, User),
                "total_licenses": await _count(session, License),
                "total_subscriptions": await _count(session, Subscription),
                "total_accounts": await _count(session, TradingAccount),
                "total_paper_trades": await _count(session, PaperTrade),
                "total_audit_logs": await _count(session, AuditLog),
            }
            logger.info("Demo seed complete: %s", summary)
            return summary
    finally:
        await engine.dispose()


async def _count(session, model) -> int:
    result = await session.execute(select(func.count()).select_from(model))
    return int(result.scalar() or 0)


if __name__ == "__main__":
    _require_dev_database()
    asyncio.run(seed())

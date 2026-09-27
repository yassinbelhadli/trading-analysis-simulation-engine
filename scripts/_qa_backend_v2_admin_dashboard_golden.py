"""Capture or compare a golden master for the existing admin overview read."""
from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

GOLDEN_PATH = ROOT / "tests" / "backend_v2_admin_dashboard_golden.json"
ADMIN_EMAIL = "golden-admin@testmail.com"
CLIENT_EMAIL = "golden-admin-client@testmail.com"
SECOND_CLIENT_EMAIL = "golden-admin-client-2@testmail.com"
ADMIN_ID = "00000000-0000-0000-0000-000000000301"
CLIENT_ID = "00000000-0000-0000-0000-000000000302"
SECOND_CLIENT_ID = "00000000-0000-0000-0000-000000000303"
ACCOUNT_ID = "00000000-0000-0000-0000-000000000304"
TRADE_ID = "00000000-0000-0000-0000-000000000305"
LICENSE_ID = "00000000-0000-0000-0000-000000000306"


def _json(value: Any) -> Any:
    """Convert database values into JSON-safe values."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json(v) for v in value]
    return value


def _canonicalize(value: Any, aliases: dict[str, str], key: str | None = None) -> Any:
    """Normalize generated identifiers and health timestamps."""
    if isinstance(value, dict):
        return {
            str(k): _canonicalize(v, aliases, str(k))
            for k, v in sorted(value.items())
        }
    if isinstance(value, list):
        return [_canonicalize(item, aliases, key) for item in value]
    if isinstance(value, str):
        for raw_id, alias in aliases.items():
            if value == raw_id:
                return alias
            value = value.replace(raw_id, alias)
        if key == "id":
            return "<id>"
        if key and (key.endswith("_at") or key in {"timestamp", "started_at"}):
            return "<timestamp>"
    if key in {"pid", "instance_id", "uptime_hours", "cycles", "heartbeat_age_sec", "memory_mb", "cpu_percent"}:
        return "<dynamic>"
    return value


def _row_state(row: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    """Serialize selected model fields without ORM state or secrets."""
    return {field: _json(getattr(row, field)) for field in fields}


async def _reset_and_seed() -> None:
    """Reset the dedicated admin fixture in the QA database."""
    from sqlalchemy import delete, select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from database.base import Base
    from database.models import (
        AccountScan,
        AuditLog,
        License,
        LoginSession,
        PaperTrade,
        RiskProfile,
        Role,
        SupportTicket,
        Subscription,
        TradingAccount,
        User,
        VerificationToken,
    )
    from security.access_control import seed_roles_and_permissions
    from security.password import hash_password

    database_url = importlib.import_module("_qa_client_sprint1").os.environ["DATABASE_URL"]
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with factory() as session:
            await seed_roles_and_permissions(session)
            all_accounts = list((await session.execute(select(TradingAccount))).scalars().all())
            for account in all_accounts:
                await session.execute(delete(PaperTrade).where(PaperTrade.account_id == account.id))
                await session.execute(delete(AccountScan).where(AccountScan.account_id == account.id))
                await session.execute(delete(RiskProfile).where(RiskProfile.account_id == account.id))
            await session.execute(delete(PaperTrade))
            await session.execute(delete(AccountScan))
            await session.execute(delete(RiskProfile))
            await session.execute(delete(AuditLog))
            await session.execute(delete(TradingAccount))
            await session.execute(delete(License))
            await session.execute(delete(Subscription))
            await session.execute(delete(LoginSession))
            await session.execute(delete(VerificationToken))
            await session.execute(delete(SupportTicket))
            await session.execute(delete(User))

            roles = {
                role.name: role.id
                for role in (await session.execute(select(Role).where(Role.name.in_(["admin", "client"])))).scalars().all()
            }
            now = datetime.now(timezone.utc)
            password = importlib.import_module("_qa_client_sprint1").PASSWORD
            session.add_all([
                User(
                    id=ADMIN_ID,
                    email=ADMIN_EMAIL,
                    password_hash=hash_password(password),
                    role_id=roles.get("admin"),
                    account_status="active",
                    email_verified=True,
                    first_name="Golden",
                    last_name="Admin",
                ),
                User(
                    id=CLIENT_ID,
                    email=CLIENT_EMAIL,
                    password_hash=hash_password(password),
                    role_id=roles.get("client"),
                    account_status="active",
                    email_verified=True,
                    first_name="Golden",
                    last_name="Client",
                ),
                User(
                    id=SECOND_CLIENT_ID,
                    email=SECOND_CLIENT_EMAIL,
                    password_hash=hash_password(password),
                    role_id=roles.get("client"),
                    account_status="active",
                    email_verified=True,
                    first_name="Second",
                    last_name="Client",
                ),
                Subscription(
                    user_id=CLIENT_ID,
                    plan="professional",
                    billing_cycle="monthly",
                    price=59.0,
                    start_date=now - timedelta(days=2),
                    end_date=now + timedelta(days=28),
                    active=True,
                ),
                License(
                    id=LICENSE_ID,
                    user_id=CLIENT_ID,
                    license_key="GOLDEN-ADMIN-LICENSE",
                    plan="professional",
                    status="active",
                    max_accounts=3,
                    expires_at=now + timedelta(days=28),
                ),
                TradingAccount(
                    id=ACCOUNT_ID,
                    user_id=CLIENT_ID,
                    account_type="FUNDED",
                    platform="MT5",
                    account_fingerprint="golden-admin-fingerprint",
                    active=True,
                    verified=True,
                    engine_status="ACTIVE",
                    balance_snapshot=10000.0,
                    equity_snapshot=10000.0,
                    login="9301",
                    license_id=LICENSE_ID,
                ),
                PaperTrade(
                    id=TRADE_ID,
                    user_id=CLIENT_ID,
                    account_id=ACCOUNT_ID,
                    symbol="XAUUSD",
                    direction="BUY",
                    entry_price=1.0,
                    stop_loss=0.9,
                    take_profit=1.1,
                    status="OPEN",
                    created_at=now,
                ),
                AuditLog(
                    user_id=CLIENT_ID,
                    event_type="system.error",
                    severity="ERROR",
                    source="golden",
                    message="Golden error",
                    created_at=now,
                ),
            ])
            await session.commit()
    finally:
        await engine.dispose()


async def _snapshot() -> dict[str, Any]:
    """Read the fixture source rows with a fresh session."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from database.models import AuditLog, License, PaperTrade, Subscription, TradingAccount, User

    database_url = importlib.import_module("_qa_client_sprint1").os.environ["DATABASE_URL"]
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            users = list((await session.execute(
                select(User).where(User.id.in_([ADMIN_ID, CLIENT_ID, SECOND_CLIENT_ID])).order_by(User.id)
            )).scalars().all())
            licenses = list((await session.execute(
                select(License).where(License.user_id.in_([CLIENT_ID])).order_by(License.id)
            )).scalars().all())
            accounts = list((await session.execute(
                select(TradingAccount).where(TradingAccount.user_id.in_([CLIENT_ID])).order_by(TradingAccount.id)
            )).scalars().all())
            trades = list((await session.execute(
                select(PaperTrade).where(PaperTrade.user_id.in_([CLIENT_ID])).order_by(PaperTrade.id)
            )).scalars().all())
            subscriptions = list((await session.execute(
                select(Subscription).where(Subscription.user_id.in_([CLIENT_ID])).order_by(Subscription.id)
            )).scalars().all())
            audits = list((await session.execute(
                select(AuditLog).where(AuditLog.user_id.in_([ADMIN_ID, CLIENT_ID, SECOND_CLIENT_ID])).order_by(AuditLog.created_at, AuditLog.id)
            )).scalars().all())
            raw = {
                "users": [_row_state(row, ("id", "email", "role_id", "account_status")) for row in users],
                "licenses": [_row_state(row, ("id", "user_id", "status", "max_accounts")) for row in licenses],
                "accounts": [_row_state(row, ("id", "user_id", "active", "engine_status")) for row in accounts],
                "trades": [_row_state(row, ("id", "user_id", "account_id", "status")) for row in trades],
                "subscriptions": [_row_state(row, ("id", "user_id", "active", "plan")) for row in subscriptions],
                "audits": [_row_state(row, ("id", "user_id", "event_type", "severity", "message", "created_at")) for row in audits],
            }
            aliases = {
                ADMIN_ID: "user.admin",
                CLIENT_ID: "user.client",
                SECOND_CLIENT_ID: "user.client2",
                ACCOUNT_ID: "account.client",
                LICENSE_ID: "license.client",
                TRADE_ID: "trade.active",
            }
            return _canonicalize(raw, aliases), aliases
    finally:
        await engine.dispose()


def _audit_delta(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return audit rows newly created by the read request."""
    before_counts = Counter(json.dumps(row, sort_keys=True) for row in before)
    delta: list[dict[str, Any]] = []
    for row in after:
        encoded = json.dumps(row, sort_keys=True)
        if before_counts[encoded]:
            before_counts[encoded] -= 1
        else:
            delta.append(row)
    return delta


def _run(mode: str) -> int:
    """Run the admin overview baseline or comparison."""
    qa = importlib.import_module("_qa_client_sprint1")
    asyncio.run(_reset_and_seed())

    from fastapi.testclient import TestClient
    from api.main import app

    with TestClient(app) as client:
        login = client.post("/auth/login", json={"email": ADMIN_EMAIL, "password": qa.PASSWORD})
        if login.status_code != 200:
            print(f"Golden master login failed: {login.status_code} {login.text}")
            return 1
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        before, aliases = asyncio.run(_snapshot())
        response = client.get("/api/admin/overview", headers=headers)
        after, _ = asyncio.run(_snapshot())
        body = _canonicalize(response.json(), aliases)
        result = {
            "request": {"method": "GET", "path": "/api/admin/overview"},
            "response": {"status": response.status_code, "body": body},
            "db_before": before,
            "db_after": after,
            "db_changed": before != after,
            "audit_delta": _audit_delta(before["audits"], after["audits"]),
        }

    if mode == "baseline":
        GOLDEN_PATH.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"Golden master written: {GOLDEN_PATH}")
        return 0
    if not GOLDEN_PATH.exists():
        print(f"Golden master missing: {GOLDEN_PATH}")
        return 1
    expected = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    if result != expected:
        print("GOLDEN MASTER: FAIL - behavior snapshot differs")
        print("EXPECTED:", json.dumps(expected, indent=2, sort_keys=True))
        print("ACTUAL:", json.dumps(result, indent=2, sort_keys=True))
        return 1
    print("GOLDEN MASTER: PASS - behavior snapshot matches")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("baseline", "compare"), required=True)
    args = parser.parse_args()
    raise SystemExit(_run(args.mode))

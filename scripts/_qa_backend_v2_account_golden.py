"""Capture or compare a behavior golden master for client account workflows."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DATABASE_URL = os.getenv("BACKEND_V2_GOLDEN_DATABASE_URL") or os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise SystemExit("Set BACKEND_V2_GOLDEN_DATABASE_URL to a dedicated QA database")
DB_NAME = DATABASE_URL.rsplit("/", 1)[-1].split("?", 1)[0]
if not (DB_NAME.endswith("_qa") or DB_NAME.endswith("_golden")):
    raise SystemExit("Golden master requires a database ending in _qa or _golden")

os.environ["DATABASE_URL"] = DATABASE_URL
ENCRYPTION_KEY = os.getenv("BACKEND_V2_GOLDEN_ENCRYPTION_KEY") or os.getenv("ENCRYPTION_KEY")
if not ENCRYPTION_KEY:
    raise SystemExit("Set BACKEND_V2_GOLDEN_ENCRYPTION_KEY for the QA fixture")
os.environ["ENCRYPTION_KEY"] = ENCRYPTION_KEY
os.environ["USE_MOCK_TELEGRAM_SCAN"] = "true"
os.environ["TELEGRAM_BOT_TOKEN"] = ""
os.environ["TELEGRAM_TEST_MODE"] = "false"

PASSWORD = "Passw0rd!123"
EMAIL = "golden-account@testmail.com"
USER_ID = "00000000-0000-0000-0000-000000000211"
LICENSE_ID = "00000000-0000-0000-0000-000000000212"
LICENSE_KEY = "GOLDEN-ACCOUNT-LICENSE"
FIXED_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)
EXPIRES_TIME = datetime(2030, 1, 1, tzinfo=timezone.utc)
GOLDEN_PATH = ROOT / "tests" / "backend_v2_account_golden.json"


def _json(value: Any) -> Any:
    """Convert database values into JSON-safe values."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json(v) for v in value]
    return value


def _canonicalize(value: Any, account_ids: set[str], key: str | None = None) -> Any:
    """Normalize generated IDs/timestamps while preserving observable values."""
    if isinstance(value, dict):
        return {
            str(k): _canonicalize(v, account_ids, str(k))
            for k, v in sorted(value.items())
        }
    if isinstance(value, list):
        return [_canonicalize(item, account_ids, key) for item in value]
    if isinstance(value, str):
        if value == USER_ID:
            return "user.client"
        if value == LICENSE_ID:
            return "license.primary"
        if value in account_ids:
            return "account.primary"
        for account_id in account_ids:
            value = value.replace(account_id, "account.primary")
        if key == "id":
            return "<id>"
        if key and (key.endswith("_at") or key in {"last_sync"}):
            return "<timestamp>"
    return value


def _row_state(row: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    """Serialize selected model fields without credentials or SQL state."""
    return {field: _json(getattr(row, field)) for field in fields}


async def _reset_and_seed() -> None:
    """Reset only the dedicated account fixture and recreate its known state."""
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
        Subscription,
        TradingAccount,
        User,
        VerificationToken,
    )
    from security.access_control import seed_roles_and_permissions
    from security.password import hash_password

    engine = create_async_engine(DATABASE_URL)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with factory() as session:
            await seed_roles_and_permissions(session)
            old_accounts = (
                await session.execute(select(TradingAccount).where(TradingAccount.user_id == USER_ID))
            ).scalars().all()
            for account in old_accounts:
                await session.execute(delete(PaperTrade).where(PaperTrade.account_id == account.id))
                await session.execute(delete(AccountScan).where(AccountScan.account_id == account.id))
                await session.execute(delete(RiskProfile).where(RiskProfile.account_id == account.id))
            await session.execute(delete(AuditLog).where(AuditLog.user_id == USER_ID))
            await session.execute(delete(TradingAccount).where(TradingAccount.user_id == USER_ID))
            await session.execute(delete(License).where(License.user_id == USER_ID))
            await session.execute(delete(Subscription).where(Subscription.user_id == USER_ID))
            await session.execute(delete(LoginSession).where(LoginSession.user_id == USER_ID))
            await session.execute(delete(VerificationToken).where(VerificationToken.user_id == USER_ID))
            await session.execute(delete(User).where(User.id == USER_ID))

            role = (await session.execute(select(Role).where(Role.name == "client"))).scalar_one_or_none()
            session.add_all([
                User(
                    id=USER_ID,
                    email=EMAIL,
                    password_hash=hash_password(PASSWORD),
                    role_id=role.id if role else None,
                    account_status="active",
                    email_verified=True,
                    first_name="Golden",
                    last_name="Account",
                    created_at=FIXED_TIME,
                ),
                License(
                    id=LICENSE_ID,
                    user_id=USER_ID,
                    license_key=LICENSE_KEY,
                    plan="professional",
                    status="active",
                    max_accounts=3,
                    expires_at=EXPIRES_TIME,
                    transfer_locked=True,
                    created_at=FIXED_TIME,
                ),
            ])
            await session.commit()
    finally:
        await engine.dispose()


async def _raw_snapshot() -> dict[str, Any]:
    """Read account workflow state using a fresh database session."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from database.models import AccountScan, AuditLog, License, RiskProfile, TradingAccount, User

    engine = create_async_engine(DATABASE_URL)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            user = await session.get(User, USER_ID)
            licenses = (
                await session.execute(select(License).where(License.user_id == USER_ID).order_by(License.id))
            ).scalars().all()
            accounts = (
                await session.execute(select(TradingAccount).where(TradingAccount.user_id == USER_ID).order_by(TradingAccount.created_at, TradingAccount.id))
            ).scalars().all()
            account_ids = [account.id for account in accounts]
            risks = []
            scans = []
            if account_ids:
                risks = list((await session.execute(
                    select(RiskProfile).where(RiskProfile.account_id.in_(account_ids)).order_by(RiskProfile.account_id)
                )).scalars().all())
                scans = list((await session.execute(
                    select(AccountScan).where(AccountScan.account_id.in_(account_ids)).order_by(AccountScan.scanned_at, AccountScan.id)
                )).scalars().all())
            audits = list((await session.execute(
                select(AuditLog).where(AuditLog.user_id == USER_ID).order_by(AuditLog.created_at, AuditLog.id)
            )).scalars().all())
            raw = {
                "user": _row_state(user, ("id", "email", "email_verified", "account_status")) if user else None,
                "licenses": [_row_state(lic, (
                    "id", "user_id", "license_key", "status", "max_accounts", "expires_at",
                    "bound_account_id", "bound_at", "transfer_locked", "created_at",
                )) for lic in licenses],
                "accounts": [_row_state(account, (
                    "id", "user_id", "license_id", "engine_status", "active", "verified",
                    "real_trading_enabled", "removed_at", "created_at", "balance_snapshot",
                    "equity_snapshot", "broker", "platform", "server", "login",
                )) for account in accounts],
                "risk_profiles": [_row_state(risk, (
                    "id", "account_id", "mode", "drawdown_type", "initial_balance",
                )) for risk in risks],
                "scans": [_row_state(scan, (
                    "id", "account_id", "broker_detected", "balance_detected",
                    "equity_detected", "leverage_detected", "symbols_detected", "scan_status",
                )) for scan in scans],
                "audits": [_row_state(audit, (
                    "id", "user_id", "account_id", "event_type", "severity", "source",
                    "message", "payload_json", "created_at",
                )) for audit in audits],
            }
            return {"raw": raw, "account_ids": set(account_ids)}
    finally:
        await engine.dispose()


def _canonical_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Canonicalize one raw database snapshot."""
    return _canonicalize(snapshot["raw"], snapshot["account_ids"])


def _audit_delta(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return normalized audit rows newly created by one operation."""
    before_counts = Counter(json.dumps(row, sort_keys=True) for row in before)
    delta: list[dict[str, Any]] = []
    for row in after:
        encoded = json.dumps(row, sort_keys=True)
        if before_counts[encoded]:
            before_counts[encoded] -= 1
        else:
            delta.append(row)
    return delta


def _redact_body(body: Any) -> Any:
    """Redact account credentials from the golden request."""
    if not isinstance(body, dict):
        return body
    return {key: "<redacted>" if key in {"password", "token", "secret"} else value
            for key, value in body.items()}


def _patch_connector() -> None:
    """Keep the invalid-login scenario identical to the existing QA fixture."""
    from telegram_bot.services.mt_connector import MTAccountScanResult, mt_connector

    async def _fake_test(login_data):
        if login_data.login == "000000":
            return MTAccountScanResult(
                success=False,
                state="CONNECTION_FAILED",
                message="Invalid login",
                platform=login_data.platform,
                server=login_data.server,
                login=login_data.login,
                broker_name=None,
                account_balance=0.0,
                account_equity=0.0,
                account_currency="USD",
                detected_symbols=[],
                supported_markets=[],
            )
        return mt_connector._mock_result(login_data)

    mt_connector.test_connection = _fake_test


def _capture(client: Any, envelopes: list[dict[str, Any]], method: str, path: str, body: Any = None) -> Any:
    """Capture request, response, DB state, and audit changes."""
    before_raw = asyncio.run(_raw_snapshot())
    response = client.request(method, path, json=body) if body is not None else client.request(method, path)
    after_raw = asyncio.run(_raw_snapshot())
    account_ids = before_raw["account_ids"] | after_raw["account_ids"]
    before = _canonicalize(before_raw["raw"], account_ids)
    after = _canonicalize(after_raw["raw"], account_ids)
    response_body = _canonicalize(response.json(), account_ids)
    envelopes.append({
        "request": {
            "method": method,
            "path": _canonicalize(path, account_ids),
            "body": _canonicalize(_redact_body(body), account_ids),
        },
        "response": {"status": response.status_code, "body": response_body},
        "db_before": before,
        "db_after": after,
        "db_changed": before != after,
        "audit_delta": _audit_delta(before["audits"], after["audits"]),
    })
    return response


def _reset_and_seed_sync() -> None:
    """Run the async fixture reset from the command-line entry point."""
    asyncio.run(_reset_and_seed())


def _run(mode: str) -> int:
    """Run the account baseline or compare the current implementation."""
    _reset_and_seed_sync()

    from fastapi.testclient import TestClient
    from api.main import app
    _patch_connector()

    envelopes: list[dict[str, Any]] = []
    add_body = {
        "platform": "MT5",
        "server": "Golden-Demo",
        "login": "123456",
        "password": "secret",
        "name": "Golden Account",
    }
    with TestClient(app) as client:
        login = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
        if login.status_code != 200:
            print(f"Golden master login failed: {login.status_code} {login.text}")
            return 1
        client.headers.update({"Authorization": f"Bearer {login.json()['access_token']}"})

        _capture(client, envelopes, "GET", "/api/client/accounts")
        added = _capture(client, envelopes, "POST", "/api/client/accounts", add_body)
        account_id = added.json().get("account", {}).get("id")
        if not account_id:
            print(f"Golden master add failed: {added.status_code} {added.text}")
            return 1
        _capture(client, envelopes, "GET", "/api/client/accounts")
        _capture(client, envelopes, "POST", "/api/client/accounts", add_body)
        _capture(client, envelopes, "POST", "/api/client/accounts", {**add_body, "login": "000000"})
        _capture(client, envelopes, "PATCH", f"/api/client/accounts/{account_id}", {"name": "Renamed Golden"})
        _capture(client, envelopes, "POST", f"/api/client/accounts/{account_id}/disconnect")
        _capture(client, envelopes, "POST", f"/api/client/accounts/{account_id}/reconnect", {})
        _capture(client, envelopes, "DELETE", f"/api/client/accounts/{account_id}")
        _capture(client, envelopes, "GET", "/api/client/accounts")
        _capture(client, envelopes, "DELETE", f"/api/client/accounts/{account_id}")

    result = {
        "version": 1,
        "fixture": {"database": DB_NAME, "user": "user.client", "license": "license.primary"},
        "scenarios": envelopes,
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
        for index, (old, new) in enumerate(zip(expected["scenarios"], result["scenarios"]), start=1):
            if old != new:
                print(f"First differing scenario: {index}")
                print("EXPECTED:", json.dumps(old, indent=2, sort_keys=True))
                print("ACTUAL:", json.dumps(new, indent=2, sort_keys=True))
                break
        return 1
    print("GOLDEN MASTER: PASS - behavior snapshot matches")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("baseline", "compare"), required=True)
    args = parser.parse_args()
    raise SystemExit(_run(args.mode))

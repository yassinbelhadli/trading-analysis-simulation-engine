"""Capture or compare a behavior golden master for the client license API.

This runner is intentionally test-only. It uses a dedicated QA database guard,
sanitizes generated values, and records HTTP plus database/audit state before
and after every license operation.
"""
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
EMAIL = "golden-license@testmail.com"
USER_ID = "00000000-0000-0000-0000-000000000201"
LICENSE_ID = "00000000-0000-0000-0000-000000000202"
ACCOUNT_ID = "00000000-0000-0000-0000-000000000203"
LICENSE_KEY = "GOLDEN-LICENSE-001"
FIXED_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)
EXPIRES_TIME = datetime(2030, 1, 1, tzinfo=timezone.utc)
GOLDEN_PATH = ROOT / "tests" / "backend_v2_license_golden.json"

ID_ALIASES = {
    USER_ID: "user.client",
    LICENSE_ID: "license.primary",
    ACCOUNT_ID: "account.primary",
}


def _normalize(value: Any, key: str | None = None) -> Any:
    """Normalize generated values while retaining observable behavior."""
    if isinstance(value, datetime):
        return "<timestamp>"
    if isinstance(value, dict):
        return {str(k): _normalize(v, str(k)) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return [_normalize(item, key) for item in value]
    if isinstance(value, str):
        if value in ID_ALIASES:
            return ID_ALIASES[value]
        for raw_id, alias in ID_ALIASES.items():
            value = value.replace(raw_id, alias)
        if key == "id":
            return "<id>"
        if key and key.endswith("_at"):
            return "<timestamp>"
        return value
    return value


def _json(value: Any) -> Any:
    """Convert a database or HTTP value into a JSON-safe normalized value."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json(v) for v in value]
    return value


async def _reset_and_seed() -> None:
    """Reset only the dedicated golden fixture and recreate its known state."""
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
            user = User(
                id=USER_ID,
                email=EMAIL,
                password_hash=hash_password(PASSWORD),
                role_id=role.id if role else None,
                account_status="active",
                email_verified=True,
                first_name="Golden",
                last_name="License",
                created_at=FIXED_TIME,
            )
            license_row = License(
                id=LICENSE_ID,
                user_id=USER_ID,
                license_key=LICENSE_KEY,
                plan="professional",
                status="active",
                max_accounts=2,
                expires_at=EXPIRES_TIME,
                transfer_locked=True,
                created_at=FIXED_TIME,
            )
            account = TradingAccount(
                id=ACCOUNT_ID,
                user_id=USER_ID,
                platform="MT5",
                server="Golden-Demo",
                login="123456",
                name="Golden Account",
                account_type="PERSONAL",
                account_fingerprint="golden-fingerprint",
                engine_status="WAITING_ACTIVATION",
                verified=True,
                active=True,
                real_trading_enabled=False,
                created_at=FIXED_TIME,
            )
            session.add_all([user, license_row, account])
            await session.commit()
    finally:
        await engine.dispose()


def _row_state(row: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    """Serialize selected model fields without secrets or SQLAlchemy state."""
    return {field: _json(getattr(row, field)) for field in fields}


async def _snapshot() -> dict[str, Any]:
    """Read the relevant fixture rows through a fresh database session."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from database.models import AuditLog, License, TradingAccount, User

    engine = create_async_engine(DATABASE_URL)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            user = await session.get(User, USER_ID)
            licenses = (
                await session.execute(select(License).where(License.user_id == USER_ID).order_by(License.id))
            ).scalars().all()
            accounts = (
                await session.execute(select(TradingAccount).where(TradingAccount.user_id == USER_ID).order_by(TradingAccount.id))
            ).scalars().all()
            audits = (
                await session.execute(
                    select(AuditLog).where(AuditLog.user_id == USER_ID).order_by(AuditLog.created_at, AuditLog.id)
                )
            ).scalars().all()
            return _normalize({
                "user": _row_state(user, ("id", "email", "email_verified", "account_status")) if user else None,
                "licenses": [
                    _row_state(lic, (
                        "id", "user_id", "license_key", "plan", "status", "max_accounts",
                        "expires_at", "bound_account_id", "bound_at", "telegram_id",
                        "transfer_locked", "created_at",
                    )) for lic in licenses
                ],
                "accounts": [
                    _row_state(account, (
                        "id", "user_id", "license_id", "engine_status", "active", "verified",
                        "removed_at", "created_at",
                    )) for account in accounts
                ],
                "audits": [
                    _row_state(audit, (
                        "id", "user_id", "account_id", "event_type", "severity", "source",
                        "message", "payload_json", "created_at",
                    )) for audit in audits
                ],
            })
    finally:
        await engine.dispose()


def _audit_delta(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return normalized audit rows newly added by an operation."""
    before_counts = Counter(json.dumps(row, sort_keys=True) for row in before)
    delta: list[dict[str, Any]] = []
    for row in after:
        encoded = json.dumps(row, sort_keys=True)
        if before_counts[encoded]:
            before_counts[encoded] -= 1
        else:
            delta.append(row)
    return delta


def _request_body(body: Any) -> Any:
    """Remove credentials before a request is written to the golden file."""
    if not isinstance(body, dict):
        return body
    return {key: "<redacted>" if key in {"password", "token", "secret"} else value
            for key, value in body.items()}


def _capture(client: Any, envelopes: list[dict[str, Any]], method: str, path: str, body: Any = None) -> Any:
    """Capture one request, response, database state, and audit delta."""
    before = asyncio.run(_snapshot())
    response = client.request(method, path, json=body) if body is not None else client.request(method, path)
    after = asyncio.run(_snapshot())
    envelope = {
        "request": {"method": method, "path": path, "body": _normalize(_request_body(body))},
        "response": {"status": response.status_code, "body": _normalize(response.json())},
        "db_before": before,
        "db_after": after,
        "db_changed": before != after,
        "audit_delta": _audit_delta(before["audits"], after["audits"]),
    }
    envelopes.append(envelope)
    return response


def _run(mode: str) -> int:
    """Run the baseline or compare the current license workflow."""
    _reset_and_seed_sync()

    from fastapi.testclient import TestClient
    from api.main import app

    envelopes: list[dict[str, Any]] = []
    with TestClient(app) as client:
        login = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
        if login.status_code != 200:
            print(f"Golden master login failed: {login.status_code} {login.text}")
            return 1
        client.headers.update({"Authorization": f"Bearer {login.json()['access_token']}"})

        _capture(client, envelopes, "GET", "/api/licenses/my")
        _capture(client, envelopes, "POST", "/api/licenses/bind", {
            "license_key": LICENSE_KEY,
            "account_id": ACCOUNT_ID,
        })
        _capture(client, envelopes, "GET", "/api/licenses/my")
        _capture(client, envelopes, "POST", "/api/licenses/bind", {
            "license_key": LICENSE_KEY,
            "account_id": ACCOUNT_ID,
        })
        _capture(client, envelopes, "POST", "/api/licenses/unbind", {"license_key": LICENSE_KEY})
        _capture(client, envelopes, "GET", "/api/licenses/my")
        _capture(client, envelopes, "POST", "/api/licenses/bind", {})
        _capture(client, envelopes, "POST", "/api/licenses/unbind", {"license_key": "UNKNOWN-LICENSE"})

    result = {
        "version": 1,
        "fixture": {
            "database": DB_NAME,
            "user": "user.client",
            "license": "license.primary",
            "account": "account.primary",
        },
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


def _reset_and_seed_sync() -> None:
    """Run the async fixture reset from the command-line entry point."""
    asyncio.run(_reset_and_seed())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("baseline", "compare"), required=True)
    args = parser.parse_args()
    raise SystemExit(_run(args.mode))

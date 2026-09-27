"""Capture or compare golden responses for the client dashboard read model."""
from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

GOLDEN_PATH = ROOT / "tests" / "backend_v2_client_dashboard_golden.json"
EMAILS = (
    "sprint-active@testmail.com",
    "sprint-expired@testmail.com",
    "sprint-suspended@testmail.com",
    "sprint-empty@testmail.com",
)


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
    """Normalize generated IDs and timestamps while preserving response values."""
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
        if key == "license_key":
            return "<license-key>"
        if key and (
            key.endswith("_at")
            or key in {"date", "created_at", "closed_at", "start_date", "end_date", "renew_date"}
        ):
            return "<timestamp>"
    return value


def _row_state(row: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    """Serialize selected model fields without ORM state or secrets."""
    return {field: _json(getattr(row, field)) for field in fields}


async def _snapshot(email: str) -> dict[str, Any]:
    """Read one user's dashboard source rows using a fresh database session."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from database.models import AuditLog, License, PaperTrade, Subscription, TradingAccount, User

    database_url = importlib.import_module("_qa_client_sprint1").os.environ["DATABASE_URL"]
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            user = (await session.execute(select(User).where(User.email == email))).scalar_one()
            licenses = list((await session.execute(
                select(License).where(License.user_id == user.id).order_by(License.created_at, License.id)
            )).scalars().all())
            accounts = list((await session.execute(
                select(TradingAccount).where(TradingAccount.user_id == user.id).order_by(TradingAccount.created_at, TradingAccount.id)
            )).scalars().all())
            trades = list((await session.execute(
                select(PaperTrade).where(PaperTrade.user_id == user.id).order_by(PaperTrade.created_at, PaperTrade.id)
            )).scalars().all())
            trades.sort(key=lambda row: (
                row.status,
                row.symbol,
                row.direction,
                row.realized_pnl is None,
                row.realized_pnl or 0,
            ))
            subscription = (await session.execute(
                select(Subscription).where(Subscription.user_id == user.id)
            )).scalar_one_or_none()
            audits = list((await session.execute(
                select(AuditLog).where(AuditLog.user_id == user.id).order_by(AuditLog.created_at, AuditLog.id)
            )).scalars().all())
            audits.sort(key=lambda row: (row.event_type, row.message, json.dumps(row.payload_json or {}, sort_keys=True)))
            raw = {
                "user": _row_state(user, (
                    "id", "email", "first_name", "last_name", "telegram_id", "telegram_username",
                )),
                "licenses": [_row_state(row, (
                    "id", "user_id", "license_key", "plan", "status", "max_accounts",
                    "expires_at", "bound_account_id", "created_at",
                )) for row in licenses],
                "accounts": [_row_state(row, (
                    "id", "user_id", "license_id", "engine_status", "active", "verified",
                    "balance_snapshot", "equity_snapshot", "created_at",
                )) for row in accounts],
                "trades": [_row_state(row, (
                    "id", "account_id", "user_id", "symbol", "direction", "status",
                    "entry_price", "stop_loss", "take_profit", "lot_size", "realized_pnl",
                    "realized_r", "close_reason", "created_at", "closed_at",
                )) for row in trades],
                "subscription": _row_state(subscription, (
                    "id", "user_id", "plan", "active", "billing_cycle", "price",
                    "start_date", "end_date",
                )) if subscription else None,
                "audits": [_row_state(row, (
                    "id", "user_id", "account_id", "event_type", "severity", "source",
                    "message", "payload_json", "created_at",
                )) for row in audits],
            }
            aliases = {user.id: "user.client"}
            aliases.update({row.id: f"license.{index}" for index, row in enumerate(licenses, 1)})
            aliases.update({row.id: f"account.{index}" for index, row in enumerate(accounts, 1)})
            aliases.update({row.id: f"trade.{index}" for index, row in enumerate(trades, 1)})
            return {"snapshot": _canonicalize(raw, aliases), "aliases": aliases}
    finally:
        await engine.dispose()


def _audit_delta(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return normalized audit rows newly added by a read operation."""
    before_counts = Counter(json.dumps(row, sort_keys=True) for row in before)
    delta: list[dict[str, Any]] = []
    for row in after:
        encoded = json.dumps(row, sort_keys=True)
        if before_counts[encoded]:
            before_counts[encoded] -= 1
        else:
            delta.append(row)
    return delta


def _capture(
    client: Any,
    envelopes: list[dict[str, Any]],
    email: str,
    headers: dict[str, str],
) -> None:
    """Capture one dashboard response and its unchanged source state."""
    before_raw = asyncio.run(_snapshot(email))
    response = client.get("/api/client/dashboard", headers=headers)
    after_raw = asyncio.run(_snapshot(email))
    aliases = {**before_raw["aliases"], **after_raw["aliases"]}
    before = _canonicalize(before_raw["snapshot"], aliases)
    after = _canonicalize(after_raw["snapshot"], aliases)
    response_body = _canonicalize(response.json(), aliases)
    envelopes.append({
        "scenario": email.split("@", 1)[0],
        "request": {"method": "GET", "path": "/api/client/dashboard"},
        "response": {"status": response.status_code, "body": response_body},
        "db_before": before,
        "db_after": after,
        "db_changed": before != after,
        "audit_delta": _audit_delta(before["audits"], after["audits"]),
    })


def _run(mode: str) -> int:
    """Run the dashboard baseline or compare the current implementation."""
    qa = importlib.import_module("_qa_client_sprint1")
    qa._run_seed()

    from fastapi.testclient import TestClient
    from api.main import app

    envelopes: list[dict[str, Any]] = []
    with TestClient(app) as client:
        for email in EMAILS:
            login = client.post("/auth/login", json={"email": email, "password": qa.PASSWORD})
            if login.status_code != 200:
                print(f"Golden master login failed: {email} {login.status_code} {login.text}")
                return 1
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
            _capture(client, envelopes, email, headers)

    result = {"version": 1, "scenarios": envelopes}
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
                print(f"First differing scenario: {index} ({new['scenario']})")
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

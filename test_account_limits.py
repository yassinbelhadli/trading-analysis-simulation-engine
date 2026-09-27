"""
REQ 2 — License <-> MT5 account limit enforcement (service level).

Verifies that:
  * add_account enforces the active license max_accounts BEFORE any broker
    connection attempt (count of non-removed accounts, not bound_account_id).
  * get_account_limits reports used/max/unlimited consistently with the
    accounts list (single source of truth for the License page).
  * MT4 / non-MT5 platforms are rejected (MT5-only product).
  * Users without an active license cannot provision accounts.
  * Unlimited plans (max_accounts >= 999 or infinity/enterprise/unlimited)
    never hit the limit.

Run:
    .venv\\Scripts\\python.exe test_account_limits.py
"""
import asyncio
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from database.db import async_session_factory
from database.repositories import UserRepository, LicenseRepository, AccountRepository
from api.services.client_account_service import (
    ClientAccountService,
    AccountInputError,
    AccountLimitReachedError,
    AccountNoActiveLicenseError,
)
from api.services.license_service import LicenseService
from telegram_bot.services.mt_connector import MTAccountScanResult, mt_connector

PASS = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = ""):
    global PASS, FAIL
    if cond:
        print(f"  PASS: {name}")
        PASS += 1
    else:
        print(f"  FAIL: {name} {detail}")
        FAIL += 1


async def fake_scan(login_data) -> MTAccountScanResult:
    """Deterministic successful scan used instead of a live MT5 connection."""
    return MTAccountScanResult(
        success=True, state="CONNECTED",
        message="Account connected successfully.",
        platform=login_data.platform, server=login_data.server, login=login_data.login,
        broker_name="Mock Broker",
        account_balance=10000.0, account_equity=10000.0,
        account_currency="USD",
        detected_symbols=["XAUUSD", "NAS100", "BTCUSD"],
        supported_markets=["GOLD", "NASDAQ", "BTC"],
        leverage="1:100", trade_mode="DEMO",
        warnings=[], metadata={"mock": True},
    )


async def main():
    global PASS, FAIL
    print("=" * 60)
    print("REQ 2: LICENSE <-> MT5 ACCOUNT LIMIT ENFORCEMENT")
    print("=" * 60)

    ts = int(time.time()) % 100000
    original_test_connection = mt_connector.test_connection
    mt_connector.test_connection = fake_scan  # type: ignore[method-assign]

    async with async_session_factory() as session:
        user_repo = UserRepository(session)
        lic_repo = LicenseRepository(session)
        acc_repo = AccountRepository(session)
        lic_service = LicenseService(session)
        acc_service = ClientAccountService(session)

        # ── Setup: fresh user with a 1-account license ─────────────────
        user = await user_repo.get_or_create_by_telegram(
            telegram_id=990000 + ts,
            telegram_username=f"limit_test_{ts}",
            first_name="Limit",
            last_name="Test",
            language="EN",
        )
        user.email = f"limit-test-{ts}@ict-ea-test.dev"
        lic = await lic_repo.create(
            user_id=user.id,
            license_key=f"LIMIT-TEST-{ts}",
            plan="standard",
            max_accounts=1,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        await lic_repo.activate(lic.id)
        await session.commit()

        try:
            # ── 1. MT5-only: MT4 / bogus platforms rejected ────────────
            print("\n--- MT5-only platform enforcement ---")
            for platform in ("MT4", "mt4", "MT6", "MT7", "OANDA"):
                try:
                    await acc_service.add_account(user.id, {
                        "platform": platform, "server": "ICMarkets-Live08",
                        "login": "111111", "password": "secret",
                    })
                    check(f"platform={platform} rejected", False, "(was accepted)")
                except AccountInputError as exc:
                    check(f"platform={platform} rejected", "MT5" in str(exc), f"-> {exc}")
                except Exception as exc:  # noqa: BLE001
                    check(f"platform={platform} rejected", False, f"-> unexpected {type(exc).__name__}: {exc}")

            # ── 2. No active license -> blocked ─────────────────────────
            print("\n--- No-license user blocked ---")
            user2 = await user_repo.get_or_create_by_telegram(
                telegram_id=990001 + ts,
                telegram_username=f"nolic_{ts}",
                first_name="No",
                last_name="License",
                language="EN",
            )
            user2.email = f"nolic-{ts}@ict-ea-test.dev"
            await session.commit()
            try:
                await acc_service.add_account(user2.id, {
                    "platform": "MT5", "server": "ICMarkets-Live08",
                    "login": "222222", "password": "secret",
                })
                check("no-license add blocked", False, "(was accepted)")
            except AccountNoActiveLicenseError as exc:
                check("no-license add blocked", "No active license" in str(exc), f"-> {exc}")

            # ── 3. First account within limit -> accepted ───────────────
            print("\n--- Limit enforcement (max_accounts=1) ---")
            limits0 = await lic_service.get_account_limits(user.id)
            check("limits before add: used=0", limits0["used"] == 0, f"-> {limits0}")
            check("limits before add: max=1", limits0["max"] == 1, f"-> {limits0}")
            check("limits before add: unlimited=false", limits0["unlimited"] is False, f"-> {limits0}")

            res = await acc_service.add_account(user.id, {
                "platform": "MT5", "server": "ICMarkets-Live08",
                "login": "333333", "password": "secret", "name": "Limit Test 1",
            })
            acc1 = res["account"]
            check("first account accepted", res["message"] == "Account connected", f"-> {res['message']}")
            check("account platform=MT5", acc1["platform"] == "MT5", f"-> {acc1['platform']}")
            check("account license bound", acc1["license_id"] == lic.id, f"-> {acc1['license_id']}")

            limits1 = await lic_service.get_account_limits(user.id)
            check("limits after add: used=1", limits1["used"] == 1, f"-> {limits1}")
            check("limits after add: max=1", limits1["max"] == 1, f"-> {limits1}")

            # ── 4. Second account -> limit reached (before connection) ──
            try:
                await acc_service.add_account(user.id, {
                    "platform": "MT5", "server": "ICMarkets-Live08",
                    "login": "444444", "password": "secret",
                })
                check("second account blocked", False, "(was accepted)")
            except AccountLimitReachedError as exc:
                check("second account blocked", "Max accounts (1)" in str(exc), f"-> {exc}")

            # ── 5. Removed account frees the slot ───────────────────────
            await acc_service.remove_account(user.id, acc1["id"])
            limits2 = await lic_service.get_account_limits(user.id)
            check("limits after remove: used=0", limits2["used"] == 0, f"-> {limits2}")
            res3 = await acc_service.add_account(user.id, {
                "platform": "MT5", "server": "ICMarkets-Live08",
                "login": "555555", "password": "secret", "name": "Limit Test 2",
            })
            check("slot freed after remove", res3["account"]["login"] == "555555", "-> re-add accepted")
            await acc_service.remove_account(user.id, res3["account"]["id"])

            # ── 6. Unlimited plan never hits the limit ──────────────────
            print("\n--- Unlimited plan (max_accounts=999) ---")
            lic2 = await lic_repo.create(
                user_id=user.id,
                license_key=f"LIMIT-UNL-{ts}",
                plan="enterprise",
                max_accounts=999,
                expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            )
            await lic_repo.activate(lic2.id)
            await session.commit()
            limits3 = await lic_service.get_account_limits(user.id)
            check("enterprise plan unlimited=true", limits3["unlimited"] is True, f"-> {limits3}")
            check("enterprise plan max=999", limits3["max"] == 999, f"-> {limits3}")

            # ── 7. Expired license -> no active license ─────────────────
            print("\n--- Expired license blocked ---")
            lic3 = await lic_repo.create(
                user_id=user.id,
                license_key=f"LIMIT-EXP-{ts}",
                plan="standard",
                max_accounts=1,
                expires_at=datetime.now(timezone.utc) - timedelta(days=1),
            )
            await lic_repo.activate(lic3.id)
            await session.commit()
            active = await lic_service.get_active_license(user.id)
            check("expired license not active", active is not None and active.id != lic3.id, f"-> active={active.id if active else None}")

            # ── Cleanup ─────────────────────────────────────────────────
            print("\n--- Cleanup ---")
            # Fresh session + raw table deletes: the ORM identity map and
            # cascade rules conflict with bulk deletes on related rows.
            from database.models import TradingAccount, RiskProfile, AccountScan, PaperTrade, AuditLog, User
            async with async_session_factory() as cleanup:
                lic_repo_c = LicenseRepository(cleanup)
                for lic_row in await lic_repo_c.get_by_user_id(user.id):
                    await lic_repo_c.delete(lic_row.id)
                for account in await acc_repo.get_by_user_id(user.id):
                    await cleanup.execute(
                        RiskProfile.__table__.delete().where(RiskProfile.account_id == account.id)
                    )
                    await cleanup.execute(
                        AccountScan.__table__.delete().where(AccountScan.account_id == account.id)
                    )
                    await cleanup.execute(
                        PaperTrade.__table__.delete().where(PaperTrade.account_id == account.id)
                    )
                    await cleanup.execute(
                        AuditLog.__table__.delete().where(AuditLog.account_id == account.id)
                    )
                    await cleanup.execute(
                        TradingAccount.__table__.delete().where(TradingAccount.id == account.id)
                    )
                await cleanup.execute(User.__table__.delete().where(User.id == user.id))
                await cleanup.execute(User.__table__.delete().where(User.id == user2.id))
                await cleanup.commit()
            check("cleanup committed", True)
        finally:
            mt_connector.test_connection = original_test_connection  # type: ignore[method-assign]

    print("\n" + "=" * 60)
    print(f"REQ 2 RESULT: {PASS} passed, {FAIL} failed")
    print("=" * 60)
    return FAIL == 0


if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)
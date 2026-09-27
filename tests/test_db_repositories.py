"""
Test each repository: User → License → TradingAccount → Scan.

Run:
    python -m tests.test_db_repositories
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database.db import async_session_factory
from database.repositories import UserRepository, LicenseRepository, AccountRepository, ScanRepository


async def test_all():
    async with async_session_factory() as session:
        user_repo = UserRepository(session)
        lic_repo = LicenseRepository(session)
        acc_repo = AccountRepository(session)
        scan_repo = ScanRepository(session)

        # ── 1. Create / get user by telegram ──────────────────────
        user = await user_repo.get_or_create_by_telegram(
            telegram_id=999001,
            telegram_username="test_user",
            first_name="Test",
            last_name="User",
            language="EN",
        )
        assert user.id is not None
        assert user.telegram_id == 999001
        assert user.language == "EN"
        print("[OK] 1. User created: id=%s, lang=%s" % (user.id, user.language))

        # update language
        await user_repo.update_language(user.id, "AR")
        await session.flush()
        updated = await user_repo.get_by_id(user.id)
        assert updated.language == "AR"
        print("[OK] 1b. Language updated to AR")

        # ── 2. Create license ─────────────────────────────────────
        lic = await lic_repo.create(
            user_id=user.id,
            license_key="TEST-LIC-001",
            plan="standard",
            max_accounts=3,
        )
        assert lic.id is not None
        assert lic.license_key == "TEST-LIC-001"
        valid = await lic_repo.is_valid("TEST-LIC-001")
        assert valid is True
        print("[OK] 2. License created: key=%s, valid=%s" % (lic.license_key, valid))

        # deactivate → invalid
        await lic_repo.deactivate(lic.id)
        await session.flush()
        valid2 = await lic_repo.is_valid("TEST-LIC-001")
        assert valid2 is False
        print("[OK] 2b. License deactivated: valid=%s" % valid2)

        # reactivate
        await lic_repo.activate(lic.id)
        await session.flush()

        # ── 3. Create trading account from wizard setup ───────────
        setup_data = {
            "account": {"type": "FUNDED"},
            "prop_firm": {
                "name": "FTMO",
                "program_name": "2-Step",
                "account_type": "Standard",
                "account_size": "100K",
                "risk": {"daily_loss": 5.0, "max_loss": 10.0, "profit_target": 10.0, "mode": "balanced"},
            },
            "broker": {},
            "platform": {
                "platform": "MT5",
                "server": "FTMO-Server3",
                "login": "123456",
                "balance": 100000.0,
                "demo_real": "DEMO",
            },
            "scan": {
                "balance_detected": 100000.0,
                "equity_detected": 99850.0,
                "leverage_detected": "1:100",
                "broker_detected": "FTMO",
            },
        }
        account = await acc_repo.create_from_wizard(
            user_id=user.id,
            setup_data=setup_data,
            encrypted_password="my_plain_password",
        )
        assert account.id is not None
        assert account.broker is None  # no broker for funded
        assert account.prop_firm == "FTMO"
        assert account.program == "2-Step"
        assert account.account_type == "FUNDED"
        assert account.account_size == 100000.0  # from platform.balance
        assert account.encrypted_password is not None
        assert account.encrypted_password != "my_plain_password"  # encrypted
        assert account.encrypted_password.startswith("gAAAAA")  # Fernet prefix
        assert account.balance_snapshot == 100000.0
        assert account.equity_snapshot == 99850.0
        assert account.leverage == "1:100"
        print("[OK] 3. TradingAccount created: id=%s, firm=%s, size=%s, balance_snap=%s" % (account.id, account.prop_firm, account.account_size, account.balance_snapshot))

        # verify & activate
        await acc_repo.verify(account.id)
        await acc_repo.activate(account.id)
        await session.flush()
        active = await acc_repo.get_active_by_user_id(user.id)
        assert len(active) == 1
        assert active[0].id == account.id
        print("[OK] 3b. Account verified & activated")

        # ── 4. Create scan ────────────────────────────────────────
        scan = await scan_repo.create(
            account_id=account.id,
            broker_detected="FTMO",
            balance_detected=100000.0,
            equity_detected=99850.0,
            leverage_detected="1:100",
            symbols_detected="XAUUSD,NAS100,BTCUSD",
            mismatches="balance:444vs100000",
            build=4500,
            timezone_detected="UTC+2",
            scan_status="passed",
        )
        assert scan.id is not None
        print("[OK] 4. Scan created: id=%s, status=%s" % (scan.id, scan.scan_status))

        # ── 5. Read latest scan ───────────────────────────────────
        latest = await scan_repo.get_latest_by_account(account.id)
        assert latest is not None
        assert latest.id == scan.id
        assert latest.balance_detected == 100000.0
        print("[OK] 5. Latest scan: id=%s, balance=%s" % (latest.id, latest.balance_detected))

        # ── 6. List all scans ─────────────────────────────────────
        all_scans = await scan_repo.get_by_account_id(account.id)
        assert len(all_scans) >= 1
        print("[OK] 6. Scans count: %s" % len(all_scans))

        # ── 7. User has relationships ─────────────────────────────
        await session.refresh(user)
        assert len(user.licenses) >= 1
        assert len(user.accounts) >= 1
        print("[OK] 7. User relationships: licenses=%s, accounts=%s" % (len(user.licenses), len(user.accounts)))

        print("\n*** ALL TESTS PASSED ***")

        # Rollback to keep DB clean for next run
        await session.rollback()


if __name__ == "__main__":
    asyncio.run(test_all())

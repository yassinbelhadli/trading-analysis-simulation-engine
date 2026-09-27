"""Seed an FTMO demo account for E2E testing."""
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import async_session_factory
from database.models import TradingAccount, User, License
from sqlalchemy import select
from security.encryption import encrypt
from security.account_fingerprint import build_account_fingerprint
from datetime import datetime, timezone

async def main():
    async with async_session_factory() as s:
        # Find the admin user
        user = (await s.execute(select(User).where(User.email == "admin@ictfunded.com"))).scalar_one()
        print(f"Using admin user: {user.id} ({user.email})")

        # Check if account already exists
        existing = (await s.execute(
            select(TradingAccount).where(TradingAccount.login == "1514130075")
        )).scalar_one_or_none()
        if existing:
            print(f"Account already exists: {existing.id}")
            existing.active = True
            existing.engine_status = "running"
            existing.user_id = user.id
            existing.account_type = "PERSONAL"
            existing.broker = "FTMO"
            existing.server = "FTMO-Demo"
            existing.platform = "MT5"
            existing.balance_snapshot = 10000.0
            existing.equity_snapshot = 10000.0
            existing.encrypted_password = encrypt('.....')
            existing.demo_real = "demo"
            existing.verified = True
            existing.currency = "USD"
            existing.leverage = "100"
            existing.account_size = 10000.0
            existing.account_fingerprint = build_account_fingerprint("MT5", "FTMO-Demo", "1514130075")
            await s.commit()
            print("Account updated and activated")
            return

        # Create new account
        fp = build_account_fingerprint("MT5", "FTMO-Demo", "1514130075")
        acc = TradingAccount(
            user_id=user.id,
            account_type="PERSONAL",
            broker="FTMO",
            platform="MT5",
            server="FTMO-Demo",
            login="1514130075",
            encrypted_password=encrypt('...'),
            name="FTMO Demo E2E Test",
            account_size=10000.0,
            demo_real="demo",
            currency="USD",
            leverage="100",
            balance_snapshot=10000.0,
            equity_snapshot=10000.0,
            symbol_mapping={},
            account_fingerprint=fp,
            verified=True,
            active=True,
            engine_status="running",
            created_at=datetime.now(timezone.utc),
        )
        s.add(acc)
        await s.commit()
        print(f"Account created: {acc.id} (login: 1514130075, server: FTMO-Demo)")

    print("Done.")

asyncio.run(main())

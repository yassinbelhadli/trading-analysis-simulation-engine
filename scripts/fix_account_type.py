"""Fix account_type from FTMO to PERSONAL for E2E test account."""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import async_session_factory
from database.models import TradingAccount
from sqlalchemy import select

async def main():
    async with async_session_factory() as s:
        acc = (await s.execute(
            select(TradingAccount).where(TradingAccount.login == "1514130075")
        )).scalar_one_or_none()
        if acc:
            print(f"Account: {acc.id}, type={acc.account_type}")
            acc.account_type = "PERSONAL"
            acc.broker = "FTMO"
            await s.commit()
            print(f"Updated account_type to PERSONAL")
        else:
            print("Account not found")

asyncio.run(main())

"""Check active trading accounts."""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.db import async_session_factory
from database.models import TradingAccount
from sqlalchemy import select

async def main():
    async with async_session_factory() as s:
        accounts = (await s.execute(
            select(TradingAccount).where(TradingAccount.active == True)
        )).scalars().all()
        print(f"Active accounts: {len(accounts)}")
        for acc in accounts:
            print(f"  {acc.login} @ {acc.server} | type={acc.account_type} | verified={acc.verified}")

asyncio.run(main())

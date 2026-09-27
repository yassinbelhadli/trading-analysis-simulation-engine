"""Deactivate old trading accounts."""
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
        print(f"Found {len(accounts)} active accounts:")
        for acc in accounts:
            print(f"  {acc.login} @ {acc.server}")
            if acc.login != "1514130075":
                acc.active = False
                acc.engine_status = "stopped"
        await s.commit()
        print("Done. Only 1514130075 is active.")
        accounts2 = (await s.execute(
            select(TradingAccount).where(TradingAccount.active == True)
        )).scalars().all()
        for acc in accounts2:
            print(f"  Active: {acc.login} @ {acc.server}")

asyncio.run(main())

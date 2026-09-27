"""Check account real_trading_enabled and trade_mode in DB."""
import asyncio
from database.db import async_session_factory
from database.repositories.account_repository import AccountRepository


async def main():
    async with async_session_factory() as session:
        repo = AccountRepository(session)
        account = await repo.get_by_login(1514130075)
        if account:
            print(f"real_trading_enabled={account.real_trading_enabled}")
            print(f"trade_mode={account.trade_mode}")
            print(f"account_type={account.account_type}")
        else:
            print("Account not found")

asyncio.run(main())

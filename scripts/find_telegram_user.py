"""Find which user has this telegram_id."""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.db import async_session_factory
from database.models import User
from sqlalchemy import select

async def main():
    async with async_session_factory() as s:
        # list all users and their telegram_ids
        result = await s.execute(select(User))
        for user in result.scalars():
            print(f"ID={user.id}, email={user.email}, telegram_id={user.telegram_id}")

        # check admin
        admin = (await s.execute(
            select(User).where(User.email == "admin@ictfunded.com")
        )).scalar_one()
        print(f"\nAdmin email={admin.email}, telegram_id={admin.telegram_id}")

asyncio.run(main())

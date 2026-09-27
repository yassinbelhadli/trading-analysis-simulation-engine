"""Set admin user's telegram_id to enable AlertService notifications."""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.db import async_session_factory
from database.models import User
from sqlalchemy import select

async def main():
    async with async_session_factory() as s:
        user = (await s.execute(
            select(User).where(User.email == "admin@ictfunded.com")
        )).scalar_one()
        print(f"User: {user.email}, telegram_id={user.telegram_id}")
        user.telegram_id = 7320801946
        await s.commit()
        print(f"telegram_id set to 7320801946")

asyncio.run(main())

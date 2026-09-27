"""Move telegram_id using raw SQL (two separate statements)."""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.db import async_session_factory
from sqlalchemy import text

async def main():
    async with async_session_factory() as s:
        # first: clear source
        await s.execute(
            text("UPDATE users SET telegram_id = NULL WHERE email = 'cimoroyassin@gmail.com'")
        )
        await s.commit()
        print("Cleared source OK")
        # second: set target
        await s.execute(
            text("UPDATE users SET telegram_id = 7320801946 WHERE email = 'admin@ictfunded.com'")
        )
        await s.commit()
        print("Set target OK")
    # verify
    async with async_session_factory() as v:
        result = await v.execute(text("SELECT email, telegram_id FROM users ORDER BY email"))
        for row in result:
            print(f"  {row.email}: telegram_id={row.telegram_id}")

asyncio.run(main())

import sys
sys.path.insert(0, ".")

import asyncio
from database.db import async_session_factory
from sqlalchemy import text

async def migrate():
    async with async_session_factory() as session:
        result = await session.execute(
            text("SELECT character_maximum_length FROM information_schema.columns "
                 "WHERE table_name = 'users' AND column_name = 'two_factor_secret'")
        )
        row = result.fetchone()
        print("Current two_factor_secret length:", row[0] if row else "column missing")

        if row and (row[0] or 0) < 512:
            await session.execute(text(
                "ALTER TABLE users ALTER COLUMN two_factor_secret TYPE VARCHAR(512)"
            ))
            await session.commit()
            print("Widened two_factor_secret to VARCHAR(512)")
        else:
            print("No change needed")

asyncio.run(migrate())

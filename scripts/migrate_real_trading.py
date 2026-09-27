import asyncio
from database.db import engine
from sqlalchemy import text


async def migrate():
    async with engine.begin() as conn:
        await conn.execute(text(
            "ALTER TABLE trading_accounts "
            "ADD COLUMN IF NOT EXISTS real_trading_enabled "
            "BOOLEAN DEFAULT FALSE"
        ))
        print("[OK] real_trading_enabled column added")
    await engine.dispose()


asyncio.run(migrate())

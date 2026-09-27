"""Add client profile columns (avatar, country) to the users table.

Run with DATABASE_URL set to the target database, e.g.:
  $env:DATABASE_URL="postgresql+asyncpg://postgres:cimoro2008@localhost:5432/ict_funded_ea"
  python scripts/migrate_client_profile.py

The QA database is recreated by the harness, but the default dev DB persists
tables, so this migration must be applied there too.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def main():
    from sqlalchemy import text
    from database.db import engine

    async with engine.begin() as conn:
        cols = await conn.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'users'"
        ))
        existing = {row[0] for row in cols.fetchall()}
        added = []
        for name, ddl in (
            ("avatar", "ALTER TABLE users ADD COLUMN avatar VARCHAR(500)"),
            ("country", "ALTER TABLE users ADD COLUMN country VARCHAR(100)"),
        ):
            if name not in existing:
                await conn.execute(text(ddl))
                added.append(name)
    print(f"Migration complete. Added columns: {added or 'none (already present)'}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

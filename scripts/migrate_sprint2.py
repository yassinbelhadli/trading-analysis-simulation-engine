"""Sprint 2 schema migration: users.preferences column + ea_builds table.

Run with DATABASE_URL set to the target database, e.g.:
  $env:DATABASE_URL="postgresql+asyncpg://postgres:cimoro2008@localhost:5432/ict_funded_ea"
  python scripts/migrate_sprint2.py

Idempotent: skips columns/tables that already exist.
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
        existing_cols = {row[0] for row in cols.fetchall()}
        if "preferences" not in existing_cols:
            await conn.execute(text("ALTER TABLE users ADD COLUMN preferences JSON"))
            print("Added users.preferences")
        else:
            print("users.preferences already present")

        tables = await conn.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        ))
        existing_tables = {row[0] for row in tables.fetchall()}
        if "ea_builds" not in existing_tables:
            await conn.execute(text("""
                CREATE TABLE ea_builds (
                    id VARCHAR(36) PRIMARY KEY,
                    version VARCHAR(30) NOT NULL UNIQUE,
                    release_notes TEXT,
                    changelog TEXT,
                    windows_file VARCHAR(255),
                    macos_file VARCHAR(255),
                    is_latest BOOLEAN NOT NULL DEFAULT FALSE,
                    released_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """))
            print("Created ea_builds")
        else:
            print("ea_builds already present")

    await engine.dispose()
    print("Migration complete.")


if __name__ == "__main__":
    asyncio.run(main())

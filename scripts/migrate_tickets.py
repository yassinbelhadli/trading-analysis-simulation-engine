import sys
sys.path.insert(0, ".")

import asyncio
from database.db import async_session_factory
from sqlalchemy import text

async def migrate():
    async with async_session_factory() as session:
        result = await session.execute(
            text("SELECT column_name FROM information_schema.columns WHERE table_name = 'support_tickets'")
        )
        cols = [r[0] for r in result]
        print("Existing columns:", cols)

        operations = {
            "category": "ALTER TABLE support_tickets ADD COLUMN category VARCHAR(50) DEFAULT 'other'",
            "escalated": "ALTER TABLE support_tickets ADD COLUMN escalated BOOLEAN DEFAULT FALSE",
            "escalated_by": "ALTER TABLE support_tickets ADD COLUMN escalated_by VARCHAR(36)",
            "replied_by": "ALTER TABLE support_tickets ADD COLUMN replied_by VARCHAR(36)",
            "closed_by": "ALTER TABLE support_tickets ADD COLUMN closed_by VARCHAR(36)",
        }

        for col, sql in operations.items():
            if col not in cols:
                await session.execute(text(sql))
                print(f"  Added column: {col}")

        await session.commit()
        print("Migration complete!")

asyncio.run(migrate())

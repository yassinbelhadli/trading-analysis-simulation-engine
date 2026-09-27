"""Check and add snapshot column to paper_trades if missing."""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import engine
from sqlalchemy import text

async def main():
    async with engine.connect() as c:
        r = await c.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='paper_trades' AND column_name='snapshot'"
        ))
        exists = r.scalar()
        print(f"snapshot column exists: {bool(exists)}")
        
        if not exists:
            print("Adding snapshot column...")
            await c.execute(text(
                "ALTER TABLE paper_trades ADD COLUMN snapshot JSONB"
            ))
            await c.commit()
            print("Column added successfully!")
        else:
            print("No action needed.")

asyncio.run(main())

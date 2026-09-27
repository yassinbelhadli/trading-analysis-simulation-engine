"""Check paper trades in DB."""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.db import async_session_factory
from database.models import PaperTrade
from sqlalchemy import select

async def main():
    async with async_session_factory() as s:
        result = await s.execute(
            select(PaperTrade).order_by(PaperTrade.created_at.desc()).limit(5)
        )
        trades = list(result.scalars().all())
        print(f"Found {len(trades)} paper trades")
        for t in trades:
            print(f"  ID={t.id} account_id={t.account_id} symbol={t.symbol} direction={t.direction}")
            print(f"    status={t.status} entry={t.entry_price} lot={t.lot_size} risk={t.risk_percent}%")
            print(f"    sl={t.stop_loss} tp={t.take_profit} rr={t.risk_reward}")
            print(f"    session={t.session} score={t.score} confidence={t.confidence}")
            print(f"    created={t.created_at} executed={t.executed_at}")

asyncio.run(main())

"""Manually fill the US100.cash PLANNED trade and verify lifecycle."""
import asyncio, sys, os, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s | %(message)s")

import MetaTrader5 as mt5
from database.db import async_session_factory
from database.models import PaperTrade
from sqlalchemy import select
from core_engine.execution.trade_lifecycle import trade_lifecycle

async def main():
    # Get current price
    if not mt5.initialize(path=r"C:\Program Files\MetaTrader 5\terminal64.exe"):
        print(f"MT5 init failed: {mt5.last_error()}")
        return
    tick = mt5.symbol_info_tick("US100.cash")
    current_price = tick.bid if tick else 0
    mt5.shutdown()
    print(f"US100.cash current price: {current_price}")

    # Find PLANNED trade
    async with async_session_factory() as s:
        trade = (await s.execute(
            select(PaperTrade).where(
                PaperTrade.symbol == "US100.cash",
                PaperTrade.status == "PLANNED"
            ).order_by(PaperTrade.created_at.desc())
        )).scalar_one_or_none()

    if not trade:
        print("No PLANNED trade found")
        return

    print(f"Trade: {trade.id} entry={trade.entry_price} fill_condition={current_price <= trade.entry_price}")

    # Check fill condition
    if trade_lifecycle.check_fill(trade, current_price):
        print("Fill condition MET — filling trade...")
        filled = await trade_lifecycle.fill_trade(trade.id, current_price)
        if filled:
            print(f"✅ FILLED: {filled.symbol} {filled.direction} @ {filled.entry_price}")
            print(f"  status={filled.status} lot={filled.lot_size}")
        else:
            print("❌ fill_trade returned None")
    else:
        print(f"⏳ Fill condition NOT met: {current_price:.2f} > {trade.entry_price}")

    # Verify final state
    async with async_session_factory() as s:
        trade2 = (await s.execute(
            select(PaperTrade).where(PaperTrade.id == trade.id)
        )).scalar_one()
        print(f"\nFinal state: status={trade2.status} executed={trade2.executed_at}")

asyncio.run(main())

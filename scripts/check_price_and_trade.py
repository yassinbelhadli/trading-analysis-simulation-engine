"""Check current US100.cash price and monitor trade."""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import MetaTrader5 as mt5
from database.db import async_session_factory
from database.models import PaperTrade, TradingAccount
from sqlalchemy import select

async def main():
    # ── 1. Check current price directly ──
    if not mt5.initialize(path=r"C:\Program Files\MetaTrader 5\terminal64.exe"):
        print(f"MT5 init failed: {mt5.last_error()}")
        return
    try:
        tick = mt5.symbol_info_tick("US100.cash")
        if tick:
            price = tick.bid
            print(f"US100.cash bid={tick.bid} ask={tick.ask} spread={tick.ask-tick.bid}")
            entry = 27484.33
            diff = price - entry
            if diff <= 0:
                print(f"  ✅ SELL fill condition MET: price={price:.2f} <= entry={entry}")
            else:
                print(f"  ⏳ SELL waiting: price={price:.2f} above entry={entry} by {diff:.2f}")
        else:
            print(f"No tick for US100.cash")
    finally:
        mt5.shutdown()

    # ── 2. Check trades in DB ──
    async with async_session_factory() as s:
        result = await s.execute(
            select(PaperTrade).order_by(PaperTrade.created_at.desc()).limit(5)
        )
        for t in result.scalars():
            status_icon = {"PLANNED": "⏳", "FILLED": "✅", "CLOSED": "✅", "CANCELLED": "❌"}.get(t.status, "❓")
            print(f"\n{status_icon} Trade: {t.id[:8]}... {t.symbol} {t.direction} | status={t.status}")
            print(f"    entry={t.entry_price} sl={t.stop_loss} tp={t.take_profit} rr={t.risk_reward}")
            print(f"    lot={t.lot_size} risk={t.risk_percent}% score={t.score}")
            print(f"    created={t.created_at}")
            if t.executed_at:
                print(f"    executed={t.executed_at}")
            if t.exit_price:
                print(f"    exit={t.exit_price} pnl={t.realized_pnl} reason={t.close_reason}")

asyncio.run(main())

"""Test _get_current_price fix with symbol_info_tick."""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core_engine.mt5_runtime import MT5Runtime
from core_engine.mt_runtime import MTConnectionConfig

async def main():
    cfg = MTConnectionConfig(login=1514130075, server="FTMO-Demo", password=".....", platform="MT5")
    rt = MT5Runtime(cfg)
    ok = await rt.connect()
    print(f"Connect: {ok}")
    if not ok:
        return

    for sym in ["US100.cash", "XAUUSD", "BTCUSD"]:
        ticks = await rt.get_ticks(sym, 1)
        rates = await rt.get_rates(sym, 1, 1)
        if ticks:
            t = ticks[0]
            print(f"\n{sym}: bid={t.bid} ask={t.ask} spread={t.ask-t.bid:.2f}")
        elif rates and isinstance(rates, list):
            last = rates[-1]
            close = last.get("close") if isinstance(last, dict) else 0
            print(f"\n{sym}: NO TICK data — get_rates close={close} ⚠️")
        else:
            print(f"\n{sym}: NO data at all ❌")

    await rt.disconnect()

asyncio.run(main())

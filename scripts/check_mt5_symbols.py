"""Check MT5 symbol trading status."""
import MetaTrader5 as mt5

mt5.initialize(path=r"C:\Program Files\MetaTrader 5\terminal64.exe")
for sym in ["US100.cash", "XAUUSD", "BTCUSD"]:
    info = mt5.symbol_info(sym)
    if info:
        d = info._asdict()
        print(f"{sym}:")
        print(f"  trade_mode={d['trade_mode']} (0=disabled,1=long,2=short,3=both)")
        print(f"  bid={d['bid']} ask={d['ask']}")
        print(f"  spread={d['spread']} stops_level={d['trade_stops_level']}")
        print(f"  session_deals={d['session_deals']} session_profit={d['session_profit']}")
        print()
mt5.shutdown()

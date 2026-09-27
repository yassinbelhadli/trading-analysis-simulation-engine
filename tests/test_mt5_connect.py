"""Quick MT5 connectivity test."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import MetaTrader5 as mt5

LOGIN = int(os.environ.get("MT5_LOGIN", "1514130075"))
PASSWORD = os.environ.get("MT5_PASSWORD", '......')
SERVER = os.environ.get("MT5_SERVER", "FTMO-Demo")

print(f"MT5 version: {mt5.__version__}")
init = mt5.initialize()
print(f"Initialize: {init}")
if not init:
    print(f"Error: {mt5.last_error()}")
    sys.exit(1)

print(f"Terminal info: {mt5.terminal_info()}")
auth = mt5.login(LOGIN, password=PASSWORD, server=SERVER)
print(f"Login: {auth}")
if not auth:
    print(f"Login error: {mt5.last_error()}")
    mt5.shutdown()
    sys.exit(1)

ai = mt5.account_info()
print(f"Account: {ai.login} | Balance={ai.balance} {ai.currency} | Demo={ai.trade_mode == 0} | Leverage=1:{ai.leverage}")

symbols = mt5.symbols_get()
print(f"Symbols loaded: {len(symbols)}")
majors = ["EURUSD", "GBPUSD", "XAUUSD", "NAS100", "BTCUSD"]
found = [s for s in majors if mt5.symbol_info(s) is not None]
print(f"Major symbols found: {found}")

ticks = mt5.copy_ticks_from("EURUSD", 0, 5)
print(f"EURUSD ticks: {len(ticks) if ticks is not None else 'N/A'}")

rates = mt5.copy_rates_from_pos("EURUSD", mt5.TIMEFRAME_M5, 0, 5)
print(f"EURUSD M5 candles: {len(rates) if rates is not None else 'N/A'}")
if rates is not None and len(rates) > 0:
    last = rates[-1]
    print(f"Latest: O={last.open} H={last.high} L={last.low} C={last.close}")

positions = mt5.positions_get()
print(f"Open positions: {len(positions) if positions is not None else 0}")

orders = mt5.orders_get()
print(f"Pending orders: {len(orders) if orders is not None else 0}")

mt5.shutdown()
print("\n=== MT5 CONNECTION OK ===")

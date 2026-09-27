"""Simple script: check MT5 config, connect, and try to place an order."""
import MetaTrader5 as mt5

path = r"C:\Program Files\MetaTrader 5\terminal64.exe"
login = 1514130075
password = "..."
server = "FTMO-Demo"

# Kill existing terminals first
import subprocess, time
subprocess.run(["taskkill", "/f", "/im", "terminal64.exe"], capture_output=True)
time.sleep(3)

if not mt5.initialize(path=path, login=login, password=password, server=server, timeout=30000):
    print(f"Init failed: {mt5.last_error()}")
    exit(1)

time.sleep(3)
term = mt5.terminal_info()
print(f"trade_allowed={term.trade_allowed} connected={term.connected}")

if not term.trade_allowed:
    print("AutoTrading still OFF")
    mt5.shutdown()
    exit(1)

print("AutoTrading ON - attempting order")
tick = mt5.symbol_info_tick("US100.cash")
print(f"bid={tick.bid} ask={tick.ask}")

request = {
    "action": mt5.TRADE_ACTION_DEAL,
    "symbol": "US100.cash",
    "volume": 0.01,
    "type": mt5.ORDER_TYPE_SELL,
    "price": tick.bid,
    "deviation": 20,
    "magic": 123456,
    "comment": "E2E test",
    "type_time": mt5.ORDER_TIME_GTC,
    "type_filling": mt5.ORDER_FILLING_IOC,
}
result = mt5.order_send(request)
print(f"Order: retcode={result.retcode} ({result.comment})")

if result.retcode == mt5.TRADE_RETCODE_DONE:
    print("ORDER PLACED SUCCESSFULLY")
else:
    codes = {
        10014: "MARKET_CLOSED", 10004: "NO_MONEY",
        10027: "AUTOTRADING_OFF", 10006: "OFF_QUOTES",
    }
    print(f"FAILED: {codes.get(result.retcode, 'UNKNOWN')} ({result.retcode})")

pos = mt5.positions_get(symbol="US100.cash")
if pos:
    for p in pos:
        print(f"Position: ticket={p.ticket} type={'SELL' if p.type==1 else 'BUY'} vol={p.volume} profit={p.profit}")
else:
    print("No positions")

mt5.shutdown()

"""Initialize MT5 with credentials and test order."""
import MetaTrader5 as mt5
import sys

path = r"C:\Program Files\MetaTrader 5\terminal64.exe"
login = 1514130075
password = "....."
server = "FTMO-Demo"

# Initialize with credentials
print(f"Initializing MT5: login={login} server={server}")
print(f"  path={path}")
sys.stdout.flush()

result = mt5.initialize(
    path=path,
    login=login,
    password=password,
    server=server,
    timeout=30000,
)
print(f"Initialize result: {result}")
sys.stdout.flush()

if not result:
    err = mt5.last_error()
    print(f"Init FAILED: {err}")
    sys.stdout.flush()
    mt5.shutdown()
    exit(1)

# Check terminal
term = mt5.terminal_info()
print(f"Terminal: trade_allowed={term.trade_allowed} connected={term.connected}")
sys.stdout.flush()

# Check account
acc = mt5.account_info()
print(f"Account: {acc.login}@{acc.server} balance={acc.balance} trade_mode={acc.trade_mode}")
sys.stdout.flush()

# Try an order
tick = mt5.symbol_info_tick("US100.cash")
if not tick:
    print("No tick data")
    mt5.shutdown()
    exit(1)

print(f"US100.cash: bid={tick.bid} ask={tick.ask}")
sys.stdout.flush()

request = {
    "action": mt5.TRADE_ACTION_DEAL,
    "symbol": "US100.cash",
    "volume": 0.01,
    "type": mt5.ORDER_TYPE_SELL,
    "price": tick.bid,
    "deviation": 20,
    "magic": 123456,
    "comment": "Test SELL",
    "type_time": mt5.ORDER_TIME_GTC,
    "type_filling": mt5.ORDER_FILLING_IOC,
}
result = mt5.order_send(request)
print(f"Order: retcode={result.retcode} ({result.comment})")
sys.stdout.flush()

if result.retcode == mt5.TRADE_RETCODE_DONE:
    print("ORDER PLACED!")
else:
    codes = {
        10014: "MARKET_CLOSED", 10004: "NO_MONEY", 10027: "AUTOTRADING_OFF",
        10006: "OFF_QUOTES", 10015: "INVALID_FILL",
    }
    print(f"FAILED: {codes.get(result.retcode, 'UNKNOWN')}")

# Show positions
pos = mt5.positions_get(symbol="US100.cash")
if pos:
    for p in pos:
        print(f"  Position: ticket={p.ticket} vol={p.volume} profit={p.profit}")
else:
    print("No positions")

mt5.shutdown()

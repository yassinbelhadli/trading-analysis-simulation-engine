"""Enable AutoTrading in MT5 terminal."""
import MetaTrader5 as mt5

# Initialize with path to the terminal
path = r"C:\Program Files\MetaTrader 5\terminal64.exe"
if not mt5.initialize(path=path):
    print(f"Init failed: {mt5.last_error()}")
    exit(1)

# Check terminal info
term = mt5.terminal_info()
if term:
    d = term._asdict()
    print("Terminal info:")
    for k, v in d.items():
        print(f"  {k}={v}")

# Try to enable algo trading
# In MT5 Python API, use terminal_info().trade_allowed and terminal_info().dlls_allowed
# The auto-trading button status is in terminal_info().trade_allowed
# But to actually enable it, we need the terminal's AutoTrading button ON

# One approach: restart with auto-trading flag
print(f"\ntrade_allowed={d.get('trade_allowed')}")
print(f"dlls_allowed={d.get('dlls_allowed')}")
print(f"trade_expert={d.get('trade_expert')}")

# Check if there's a method to enable
if hasattr(mt5, 'enable_autotrading'):
    result = mt5.enable_autotrading()
    print(f"enable_autotrading() returned: {result}")
else:
    print("No enable_autotrading method available")

# Try trading again
sym = "US100.cash"
tick = mt5.symbol_info_tick(sym)
if tick:
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": sym,
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
    print(f"\nOrder result: retcode={result.retcode} comment={result.comment}")
    if result.retcode == mt5.TRADE_RETCODE_DONE:
        print("✅ ORDER PLACED SUCCESSFULLY!")
    else:
        explanations = {
            10027: "AutoTrading disabled by client",
            10014: "Market closed",
            10004: "No money",
            10006: "Off quotes",
        }
        print(f"  Reason: {explanations.get(result.retcode, 'Unknown')}")

mt5.shutdown()

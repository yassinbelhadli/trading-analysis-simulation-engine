"""Test MT5 after enabling AutoTrading."""
import MetaTrader5 as mt5

path = r"C:\Program Files\MetaTrader 5\terminal64.exe"
if not mt5.initialize(path=path):
    print(f"Init failed: {mt5.last_error()}")
    exit(1)

term = mt5.terminal_info()
print(f"trade_allowed={term.trade_allowed}")
print(f"dlls_allowed={term.dlls_allowed}")
print(f"connected={term.connected}")

if not term.trade_allowed:
    print("AutoTrading still OFF")
    mt5.shutdown()
    exit(1)

print("AutoTrading is ON")
tick = mt5.symbol_info_tick("US100.cash")
print(f"US100.cash: bid={tick.bid} ask={tick.ask}")

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
print(f"Order: retcode={result.retcode} comment={result.comment}")

codes = {
    10014: "MARKET_CLOSED",
    10004: "NO_MONEY",
    10027: "AUTOTRADING_OFF",
    10006: "OFF_QUOTES",
    10015: "INVALID_FILL",
    10016: "CONNECTION",
    10008: "REQUOTE",
    10007: "BROKER_BUSY",
}
if result.retcode == mt5.TRADE_RETCODE_DONE:
    print("ORDER PLACED!")
    pos = mt5.positions_get(symbol="US100.cash")
    if pos:
        for p in pos:
            print(f"  Position: ticket={p.ticket} vol={p.volume} profit={p.profit}")
else:
    print(f"FAILED: {codes.get(result.retcode, 'UNKNOWN')} ({result.retcode})")

mt5.shutdown()

"""Close the test SELL position on US100.cash."""
import MetaTrader5 as mt5

path = r"C:\Program Files\MetaTrader 5\terminal64.exe"
if not mt5.initialize(path=path, timeout=30000):
    print(f"Init failed: {mt5.last_error()}")
    exit(1)

pos = mt5.positions_get(symbol="US100.cash")
if not pos:
    print("No positions to close")
    mt5.shutdown()
    exit(0)

for p in pos:
    ptype = "SELL" if p.type == 1 else "BUY"
    print(f"Position: ticket={p.ticket} type={ptype} vol={p.volume} profit={p.profit}")

    close_request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": "US100.cash",
        "volume": p.volume,
        "type": mt5.ORDER_TYPE_BUY,
        "position": p.ticket,
        "price": mt5.symbol_info_tick("US100.cash").ask,
        "deviation": 20,
        "magic": 123456,
        "comment": "Close test",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(close_request)
    print(f"Close order: retcode={result.retcode} ({result.comment})")
    if result.retcode == mt5.TRADE_RETCODE_DONE:
        print("POSITION CLOSED")
    else:
        print(f"Close failed")

mt5.shutdown()

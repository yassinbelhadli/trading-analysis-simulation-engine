"""Test placing a small MT5 market order on US100.cash (SELL 0.01 lot)."""
import MetaTrader5 as mt5

mt5.initialize(path=r"C:\Program Files\MetaTrader 5\terminal64.exe")

sym = "US100.cash"
info = mt5.symbol_info(sym)
tick = mt5.symbol_info_tick(sym)
print(f"{sym}: trade_mode={info.trade_mode} bid={tick.bid} ask={tick.ask}")

request = {
    "action": mt5.TRADE_ACTION_DEAL,
    "symbol": sym,
    "volume": 0.01,
    "type": mt5.ORDER_TYPE_SELL,
    "price": tick.bid,
    "deviation": 20,
    "magic": 123456,
    "comment": "Test SELL - E2E",
    "type_time": mt5.ORDER_TIME_GTC,
    "type_filling": mt5.ORDER_FILLING_IOC,
}
result = mt5.order_send(request)
print(f"Result: retcode={result.retcode} comment={result.comment}")
if result.retcode == mt5.TRADE_RETCODE_DONE:
    print(f"✅ ORDER PLACED: ticket={result.order} volume=0.01")
else:
    codes = {
        10004: "NO_MONEY", 10006: "OFF_QUOTES", 10007: "BROKER_BUSY",
        10008: "REQUOTE", 10009: "LOCKED", 10010: "LONG_ONLY",
        10011: "TOO_MANY_REQUESTS", 10012: "NO_CHANGES", 10013: "AUTOMATION_ONLY",
        10014: "MARKET_CLOSED", 10015: "INVALID_FILL", 10016: "CONNECTION",
        10017: "CLOSED", 10018: "NOT_FOUND", 10019: "ACTION_INVALID",
        10020: "DISABLED", 10021: "MODIFICATION_DENIED", 10022: "VOLUME_INVALID",
        10023: "MARKET_VETOED", 10024: "POSITION_LIMIT",
    }
    print(f"  ❌ FAILED: {codes.get(result.retcode, 'UNKNOWN')} ({result.retcode})")
    print(f"  Comment: {result.comment}")

# Check positions
positions = mt5.positions_get(symbol=sym)
if positions:
    for p in positions:
        d = p._asdict()
        print(f"\n📊 Position: ticket={d['ticket']} type={'SELL' if d['type']==1 else 'BUY'} "
              f"volume={d['volume']} price={d['price_open']} sl={d['sl']} tp={d['tp']}")
        print(f"  profit={d['profit']} swap={d['swap']} comment={d['comment']}")
else:
    print("\nNo open positions")

mt5.shutdown()

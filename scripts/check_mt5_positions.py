import MetaTrader5 as mt5
path = r"C:\Program Files\MetaTrader 5\terminal64.exe"
if not mt5.initialize(path=path, timeout=30000):
    print(f"Init failed: {mt5.last_error()}")
    exit(1)
account = mt5.account_info()
if account:
    print(f"Account: {account.login} balance={account.balance:.2f} equity={account.equity:.2f}")
positions = mt5.positions_get()
if positions:
    for p in positions:
        ptype = "SELL" if p.type == 1 else "BUY"
        print(f"ticket={p.ticket} {p.symbol} {ptype} vol={p.volume} profit={p.profit:.2f} sl={p.sl} tp={p.tp} open={p.price_open:.2f} cur={p.price_current:.2f}")
else:
    print("No open positions")
    err = mt5.last_error()
    print(f"last_error={err}")
mt5.shutdown()

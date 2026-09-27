import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

import MetaTrader5 as mt5

mt5.initialize()
account = mt5.account_info()
print(f"Account: {account.login} @ {account.server} | Balance: {account.balance} | Demo: {account.trade_mode==0}")

# Check our target symbols
TARGETS = ["XAUUSD", "US100.cash", "BTCUSD"]
print(f"\n--- Target symbols ---")
for sym in TARGETS:
    info = mt5.symbol_info(sym)
    if info:
        mt5.symbol_select(sym, True)
        info = mt5.symbol_info(sym)
        mode_str = {0: "FULL", 1: "DISABLED", 2: "LONG_ONLY", 3: "SHORT_ONLY"}.get(info.trade_mode, str(info.trade_mode))
        print(f"  {sym:15} spread={info.spread:5} digits={info.digits} "
              f"trade_mode={mode_str:12} visible={info.visible}")
    else:
        print(f"  {sym:15} NOT FOUND")

# Test normalizer
from core_engine.risk.symbol_validator import SymbolValidator
v = SymbolValidator()
print(f"\n--- Symbol normalizer ---")
for sym in TARGETS:
    norm = v.normalize_symbol(sym)
    print(f"  {sym:15} -> {norm}")

print(f"\n--- Allowed symbols check (mode_config) ---")
from core_engine.config.trading_modes import TRADING_MODES
allowed = set(TRADING_MODES["BALANCED"].allowed_symbols)
for sym in TARGETS:
    norm = v.normalize_symbol(sym)
    print(f"  {sym:15} norm={norm:10} in allowed={norm in allowed}")

mt5.shutdown()

"""Test the execution guard to see why trades are being blocked."""
import asyncio
import MetaTrader5 as mt5
from core_engine.execution.execution_guard import ExecutionGuard
from core_engine.mt_runtime import MTConnectionConfig
from core_engine.mt5_runtime import MT5Runtime

path = r"C:\Program Files\MetaTrader 5\terminal64.exe"

async def main():
    if not mt5.initialize(path=path):
        print(f"MT5 init failed: {mt5.last_error()}")
        return

    config = MTConnectionConfig(
        login=1514130075, password="....",
        server="FTMO-Demo", platform="MT5"
    )
    runtime = MT5Runtime(config)
    await runtime.connect()

    guard = ExecutionGuard(runtime, account_id="test", user_id="admin")

    checks = [
        ("validate_symbol XAUUSD", await guard.validate_symbol("XAUUSD")),
        ("validate_market_open XAUUSD", await guard.validate_market_open("XAUUSD")),
        ("validate_spread XAUUSD", await guard.validate_spread("XAUUSD")),
        ("validate_news XAUUSD", await guard.validate_news("XAUUSD")),
        ("validate_session XAUUSD", await guard.validate_session("XAUUSD", None)),
        ("validate_duplicate_trade XAUUSD SELL", await guard.validate_duplicate_trade("XAUUSD", "SELL")),
        ("validate_daily_limit XAUUSD", await guard.validate_daily_limit("XAUUSD", max_trades_total=5, max_trades_per_symbol=3)),
    ]

    for name, result in checks:
        status = "OK" if result.allowed else "BLOCKED"
        print(f"{status:8s} | {name:40s} | {result.reason or '-'}")

    mt5.shutdown()

asyncio.run(main())

"""
Manual MT5 read-only integration test.

Usage: set MT5_TEST_LOGIN, MT5_TEST_SERVER, MT5_TEST_PASSWORD env vars, then:
    python tests/manual_test_mt5_readonly.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core_engine.mt5_runtime import MT5Runtime
from core_engine.mt_runtime import MTConnectionConfig


async def main():
    login = os.getenv("MT5_TEST_LOGIN")
    server = os.getenv("MT5_TEST_SERVER")
    password = os.getenv("MT5_TEST_PASSWORD")

    if not all([login, server, password]):
        print("SKIP: Set MT5_TEST_LOGIN, MT5_TEST_SERVER, MT5_TEST_PASSWORD")
        return

    config = MTConnectionConfig(server=server, login=login, password=password, platform="MT5")
    runtime = MT5Runtime(config)

    print(f"Connecting to {server} as {login}...")
    ok = await runtime.connect()
    if not ok:
        print("FAIL: connect() returned False")
        return
    print("[OK] Connected")

    info = await runtime.account_info()
    print(f"[OK] Account: {info.login} | {info.balance} {info.currency} | Demo={info.is_demo}")
    assert info.login == int(login), "Login mismatch"
    print(f"     Balance={info.balance}, Equity={info.equity}, Leverage={info.leverage}x")

    symbols = await runtime.get_symbols()
    print(f"[OK] Symbols: {len(symbols)} loaded")
    majors = [s.name for s in symbols if s.name in ("EURUSD", "GBPUSD", "XAUUSD", "NAS100", "BTCUSD")]
    print(f"     Majors found: {majors}")

    rates = await runtime.get_rates("EURUSD", 5, 5)
    print(f"[OK] EURUSD M5: {len(rates)} candles")
    if rates:
        print(f"     Latest: O={rates[-1]['open']} H={rates[-1]['high']} "
              f"L={rates[-1]['low']} C={rates[-1]['close']} "
              f"@ {rates[-1]['time']}")

    positions = await runtime.get_positions()
    print(f"[OK] Open positions: {len(positions)}")

    orders = await runtime.get_orders()
    print(f"[OK] Pending orders: {len(orders)}")

    ticks = await runtime.get_ticks("EURUSD", 3)
    print(f"[OK] Ticks: {len(ticks)} (bid={ticks[0].bid if ticks else 'N/A'})")

    await runtime.disconnect()
    print("[OK] Disconnected")
    print("\n=== ALL READ-ONLY TESTS PASSED ===")


if __name__ == "__main__":
    asyncio.run(main())

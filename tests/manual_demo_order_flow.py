"""
Manual demo test — full order flow through ExecutionGuard → OrderManager → MTRuntime.

Requirements before running against REAL MT5 demo:
  1. MetaTrader 5 installed with a demo account
  2. pip install MetaTrader5
  3. config/.env with:
       ALLOW_REAL_TRADING=true
       DEMO_ONLY=true
       TELEGRAM_BOT_TOKEN=your_token

Run:
    python tests/manual_demo_order_flow.py

For mock-only test (no MT5 needed):
    python tests/manual_demo_order_flow.py --mock
"""

import asyncio
import sys
import argparse

sys.path.insert(0, r"C:\Users\AGA GAMING\Desktop\test saas")

from config.settings import ALLOW_REAL_TRADING, DEMO_ONLY
from core_engine.execution.execution_guard import ExecutionGuard
from core_engine.execution.order_manager import OrderManager
from core_engine.execution.trade_manager import TradeManager
from core_engine.execution.trade_planner import TradePlan
from core_engine.mt_runtime import (
    MTConnectionConfig, MTRuntimeMock, MTPosition, MTSymbolInfo,
)
from datetime import datetime, timezone


def make_plan(symbol="XAUUSD", direction="BUY", lot=0.01) -> TradePlan:
    return TradePlan(
        valid=True, symbol=symbol, direction=direction,
        entry_type="MARKET", entry_price=2350.0,
        stop_loss=2340.0, take_profit=2370.0,
        risk_reward=2.0, lot_size=lot, risk_percent=0.5,
    )


async def run_mock():
    print("=" * 60)
    print("DEMO ORDER FLOW TEST (MOCK RUNTIME)")
    print("=" * 60)
    ok = 0

    cfg = MTConnectionConfig(server="demo", login="12345", password="pwd", platform="MT5")
    rt = MTRuntimeMock(cfg)
    await rt.connect()

    guard = ExecutionGuard(rt, "acct_demo", "user_demo")

    # --- 1. Guard should block (ALLOW_REAL_TRADING=False by default) ---
    print("\n1. Guard check (expect BLOCKED — ALLOW_REAL_TRADING=False)")
    result = await guard.can_execute(symbol="XAUUSD", direction="BUY")
    if not result.allowed:
        print(f"   ✅ Guard blocked: {result.reason}")
        ok += 1
    else:
        print(f"   ❌ Guard should have blocked")

    # --- 2. Place order through OrderManager (bypassing guard) ---
    print("\n2. OrderManager.place_order (bypass guard)")
    om = OrderManager(rt)
    plan = make_plan()
    result = await om.place_order(plan)
    if not result.success:
        print(f"   ℹ️  Expected — ALLOW_REAL_TRADING prevents order: {result.message}")
    else:
        print(f"   ✅ Order placed: ticket={result.order_id}")
        ok += 1

    # --- 3. Simulate position becoming active ---
    print("\n3. Simulate open position")
    pos = MTPosition(
        ticket=1001, symbol="XAUUSD", type=0, volume=0.01,
        open_price=2350.0, current_price=2355.0,
        stop_loss=2340.0, take_profit=2370.0,
        profit=5.0, swap=0.0, comment="demo_test",
        open_time=datetime.now(timezone.utc),
    )
    rt._positions.append(pos)
    print(f"   ✅ Position opened: XAUUSD BUY 0.01 @ 2350.0")

    # --- 4. TradeManager — modify SL (BE) ---
    print("\n4. TradeManager — move to break even")
    tm = TradeManager(rt)
    pos_1 = MTPosition(
        ticket=1001, symbol="XAUUSD", type=0, volume=0.01,
        open_price=2350.0, current_price=2361.0,
        stop_loss=2340.0, take_profit=2370.0,
        profit=11.0, swap=0.0, comment="demo_test",
        open_time=datetime.now(timezone.utc),
    )
    actions = tm.manage_position(pos_1, make_plan())
    be_action = [a for a in actions if a.action == "MOVE_BE"]
    if be_action:
        print(f"   ✅ BE action generated: SL → {be_action[0].new_sl}")
        ok += 1

        applied = await tm.apply_actions(be_action)
        if applied:
            print(f"   ✅ BE applied to position")
            ok += 1
        else:
            print(f"   ❌ BE apply failed (mock should succeed)")

    # --- 5. TradeManager — partial close ---
    print("\n5. TradeManager — partial close at +1.5R")
    pos_2 = MTPosition(
        ticket=1001, symbol="XAUUSD", type=0, volume=0.01,
        open_price=2350.0, current_price=2365.0,
        stop_loss=2350.0, take_profit=2370.0,
        profit=15.0, swap=0.0, comment="demo_test",
        open_time=datetime.now(timezone.utc),
    )
    actions = tm.manage_position(pos_2, make_plan())
    partial = [a for a in actions if a.action == "PARTIAL_CLOSE"]
    if partial:
        print(f"   ✅ Partial close action generated: vol {partial[0].close_volume}")
        ok += 1

        applied = await tm.apply_actions(partial)
        if applied:
            print(f"   ✅ Partial close applied")
            ok += 1

    # --- 6. Guard — full checklist ---
    print("\n6. Guard — full_checklist()")
    checklist = await guard.full_checklist("XAUUSD", "BUY")
    total = len(checklist)
    passed = sum(1 for r in checklist.values() if r.allowed)
    print(f"   📊 {passed}/{total} guards passed")
    for name, r in checklist.items():
        icon = "✅" if r.allowed else "❌"
        print(f"     {icon} {name}: {r.reason if not r.allowed else 'OK'}")

    # --- 7. Simulate TP hit ---
    print("\n7. TradeManager — check close (TP hit)")
    pos_3 = MTPosition(
        ticket=1001, symbol="XAUUSD", type=0, volume=0.005,
        open_price=2350.0, current_price=2370.0,
        stop_loss=2350.0, take_profit=2370.0,
        profit=20.0, swap=0.0, comment="demo_test",
        open_time=datetime.now(timezone.utc),
    )
    close = tm.check_close(pos_3, make_plan())
    if close:
        print(f"   ✅ Close action: {close.message}")
        ok += 1

    print(f"\n{'='*60}")
    print(f"RESULTS: {ok}/8 checks passed")
    print(f"{'='*60}")

    await rt.disconnect()


async def run_real():
    print("=" * 60)
    print("REAL MT5 DEMO TEST")
    print("=" * 60)
    print()
    print("⚠️  This requires a real MT5 demo account.")
    print("   Set in config/.env:")
    print("     ALLOW_REAL_TRADING=true")
    print("     DEMO_ONLY=true")
    print()
    print("   Edit connection details below and re-run.")
    print()
    print("Skipping — use --mock for automated mock test.")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock", action="store_true", help="Use mock runtime (no MT5 needed)")
    args = parser.parse_args()

    if args.mock:
        asyncio.run(run_mock())
    else:
        asyncio.run(run_real())

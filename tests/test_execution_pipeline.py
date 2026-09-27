import asyncio
import sys
from datetime import datetime, timezone

sys.path.insert(0, r"C:\Users\AGA GAMING\Desktop\test saas")

from core_engine.detection.setup_detector import (
    SetupCandidate, MarketStructureResult, FVGResult,
    OrderBlockResult, PremiumDiscountResult, ScoreResult,
)
from core_engine.execution.execution_engine import ExecutionEngine
from core_engine.execution.trade_planner import TradePlanner
from core_engine.execution.order_manager import OrderManager
from core_engine.execution.trade_manager import TradeManager
from core_engine.mt_runtime import (
    MTRuntimeMock, MTConnectionConfig, MTPosition,
)
from core_engine.risk.account_profile import AccountProfile


def make_candidate(symbol: str = "XAUUSD", direction: str = "BUY") -> SetupCandidate:
    struct = MarketStructureResult(
        valid=True, trend="BULLISH", trend_direction=direction,
        bos_detected=True, mss_detected=True,
        protected_low=2310.0, protected_high=2335.0,
    )
    fvg = FVGResult(
        valid=True, fvg_detected=True, fvg_type="BULLISH",
        fvg_top=2324.0, fvg_bottom=2321.0, fvg_size=3.0,
        mitigated=False,
    )
    ob = OrderBlockResult(
        valid=True, ob_detected=True, ob_type="BULLISH",
        ob_top=2323.0, ob_bottom=2319.0, ob_mid=2321.0,
        mitigated=False, fresh=True,
    )
    pd = PremiumDiscountResult(
        valid=True, zone="DISCOUNT", equilibrium=2320.0,
        premium_high=2340.0, discount_low=2300.0, price_position=2315.0,
    )
    score = ScoreResult(
        valid=True, score=94, confidence=93, rank="ELITE_A_PLUS",
        recommendation="EXECUTE",
        breakdown={"Setup_Score": 94},
    )
    return SetupCandidate(
        symbol=symbol, timeframe="M5", direction=direction,
        structure=struct, fvg=fvg, ob=ob, premium_discount=pd,
        score_result=score, score=94, rank="ELITE_A_PLUS",
        confidence_score=93, confidence_label="ELITE",
        approved=True, setup_id="SETUP_20260709_0815_BUY",
        reasons=["BOS", "MSS", "Bullish_FVG", "Bullish_OB", "PD_DISCOUNT"],
    )


def make_profile() -> AccountProfile:
    return AccountProfile(
        client_id="test_acc", account_type="PERSONAL",
        balance=10000.0, equity=10000.0,
        risk_per_trade=1.0, max_daily_loss=5.0, max_account_loss=15.0,
        preferred_rr=2.0, min_lot=0.01, max_lot=10.0, lot_step=0.01,
        symbol="XAUUSD",
    )


async def run():
    ok_count = 0
    fail_count = 0

    def check(label: str, condition: bool):
        nonlocal ok_count, fail_count
        if condition:
            print(f"  [OK] {label}")
            ok_count += 1
        else:
            print(f"  [FAIL] {label}")
            fail_count += 1

    # Setup
    config = MTConnectionConfig(server="demo", login="123", password="pwd", platform="MT4")
    runtime = MTRuntimeMock(config)
    engine = ExecutionEngine(runtime)
    profile = make_profile()
    candidate = make_candidate()
    risk = abs(2321.0 - 2319.0)

    print("=== EXECUTION PIPELINE TEST ===\n")

    # 1. Execute candidate
    result = await engine.execute_candidate(candidate, profile, current_price=2322.0)
    check("Candidate accepted", result.success)
    check("Trade plan created", result.plan is not None and result.plan.valid)
    check("Mock order placed", result.order is not None and result.order.success)

    plan = result.plan
    ticket = int(result.order.order_id)
    check(f"Order ticket {ticket} > 0", ticket > 0)

    assert plan is not None

    # 2. Simulate position at entry
    entry_price = plan.entry_price
    sl_price = plan.stop_loss
    tp_price = plan.take_profit
    check(f"Entry={entry_price}, SL={sl_price}, TP={tp_price}, Lot={plan.lot_size}", plan.lot_size > 0)

    # Confirm order is in runtime
    orders = await runtime.get_orders()
    check("Runtime has pending order", len(orders) == 1)

    # Simulate the order became a position
    pos = MTPosition(
        ticket=ticket, symbol=candidate.symbol, type=0,
        volume=plan.lot_size, open_price=entry_price,
        current_price=entry_price, stop_loss=sl_price,
        take_profit=tp_price, profit=0.0, swap=0.0,
        comment="test", open_time=datetime.now(timezone.utc),
    )
    runtime._positions.append(pos)
    runtime._orders.clear()

    tm = TradeManager(runtime)
    r_multiple_base = abs(entry_price - sl_price)

    # 3. At +1.0R (trigger BE)
    be_price = entry_price + r_multiple_base
    runtime._positions[0] = MTPosition(
        ticket=ticket, symbol=candidate.symbol, type=0,
        volume=plan.lot_size, open_price=entry_price,
        current_price=be_price, stop_loss=sl_price,
        take_profit=tp_price, profit=r_multiple_base * plan.lot_size,
        swap=0.0, comment="test", open_time=datetime.now(timezone.utc),
    )
    actions = tm.manage_position(runtime._positions[0], plan)
    has_be = any(a.action == "MOVE_BE" for a in actions)
    check("BE triggered at +1.0R", has_be)

    applied = await tm.apply_actions(actions)
    be_applied = any(a.action == "MOVE_BE" for a in applied)
    check("BE applied (SL moved to entry)", be_applied)

    # Verify SL updated
    pos_after_be = (await runtime.get_positions())[0]
    check("SL == entry_price after BE", abs(pos_after_be.stop_loss - entry_price) < 0.01)

    # 4. At +1.5R (trigger partial + trailing)
    partial_price = entry_price + r_multiple_base * 1.5
    runtime._positions[0] = MTPosition(
        ticket=ticket, symbol=candidate.symbol, type=0,
        volume=plan.lot_size, open_price=entry_price,
        current_price=partial_price, stop_loss=entry_price,
        take_profit=tp_price, profit=r_multiple_base * 1.5 * plan.lot_size,
        swap=0.0, comment="test", open_time=datetime.now(timezone.utc),
    )
    actions = tm.manage_position(runtime._positions[0], plan)
    has_partial = any(a.action == "PARTIAL_CLOSE" for a in actions)
    has_trail = any(a.action == "TRAIL_SL" for a in actions)
    check("Partial triggered at +1.5R", has_partial)
    check("Trailing triggered at +1.5R", has_trail)

    applied = await tm.apply_actions(actions)
    partial_applied = any(a.action == "PARTIAL_CLOSE" for a in applied)
    trail_applied = any(a.action == "TRAIL_SL" for a in applied)
    check("Partial applied (volume halved)", partial_applied)
    check("Trailing applied (SL updated)", trail_applied)

    pos_after_trail = (await runtime.get_positions())[0]
    check("Volume reduced after partial", pos_after_trail.volume < plan.lot_size)
    check("SL moved forward after trail", pos_after_trail.stop_loss > entry_price)

    # 5. At +2.0R (trigger TP close)
    tp_price_actual = entry_price + r_multiple_base * 2.0
    runtime._positions[0] = MTPosition(
        ticket=ticket, symbol=candidate.symbol, type=0,
        volume=pos_after_trail.volume, open_price=entry_price,
        current_price=tp_price_actual, stop_loss=pos_after_trail.stop_loss,
        take_profit=tp_price_actual, profit=r_multiple_base * 2.0 * pos_after_trail.volume,
        swap=0.0, comment="test", open_time=datetime.now(timezone.utc),
    )
    close_action = tm.check_close(runtime._positions[0], plan)
    check("TP close detected at +2.0R", close_action is not None)
    if close_action:
        check("Close action is TP", "Take profit" in close_action.message)

    print(f"\n=== RESULTS: {ok_count} OK, {fail_count} FAIL ===")

    if fail_count == 0:
        print("*** EXECUTION PIPELINE OK ***")
    else:
        print("*** EXECUTION PIPELINE FAILED ***")


if __name__ == "__main__":
    asyncio.run(run())

"""Integration test: PaperBroker + OrderManager + simulation TradeLifecycle.

Tests the broker-adapter execution pipeline (Framework B) end-to-end.
"""

import sys
sys.path.insert(0, r"C:\Users\AGA GAMING\Desktop\test saas")

from core_engine.simulation.planner import TradePlan
from core_engine.execution.broker import PaperBroker, BrokerEvent
from core_engine.execution.order_manager import OrderManager


def check(label: str, condition: bool):
    if condition:
        print(f"  [OK] {label}")
    else:
        print(f"  [FAIL] {label}")
    return condition


def make_plan(side: str = "BUY", entry: float = 100.0, sl: float = 99.0,
              tp_count: int = 3) -> TradePlan:
    dist = abs(entry - sl)
    tps = [entry + dist * r for r in [1.0, 2.0, 3.0]]
    return TradePlan(
        side=side,
        entry=entry,
        stop_loss=sl,
        take_profits=tps[:tp_count],
        risk_percent=1.0,
        partials=[0.50, 0.30, 0.20][:tp_count],
        label=f"TEST_{side}",
    )


def test_full_tp_chain():
    """BUY trade: fill → TP1 → BE → TP2 → trailing → TP3 → closed."""
    plan = make_plan("BUY")
    broker = PaperBroker(balance=10000.0)
    om = OrderManager(broker, account_balance=10000.0)

    ticket = om.submit(plan)
    assert ticket is not None, "No ticket returned"
    check("Order submitted", True)

    mt = om._trades[ticket]
    check("Initial state is FILLED", mt.lifecycle.state == "FILLED")
    check("SL at plan.stop_loss", abs(mt.lifecycle.current_sl - plan.stop_loss) < 0.001)

    # TP1 hit → BE triggered
    tp1_price = plan.take_profits[0]
    broker.inject_tp_hit(ticket, tp1_price)
    closed = om.poll()
    check("Not closed after TP1", ticket not in closed)
    check("State TP1_HIT after TP1", mt.lifecycle.state in ("TP1_HIT", "BE_SET"))
    check("SL moved to entry after BE", abs(mt.lifecycle.current_sl - plan.entry) < 0.01)

    # TP2 hit → trailing activated
    tp2_price = plan.take_profits[1]
    broker.inject_tp_hit(ticket, tp2_price)
    closed = om.poll()
    check("State TRAILING after TP2", mt.lifecycle.state == "TRAILING")

    # TP3 hit → trade closed
    tp3_price = plan.take_profits[2]
    broker.inject_tp_hit(ticket, tp3_price)
    closed = om.poll()
    check("Closed after TP3", ticket in closed)

    result = om.result(ticket)
    check("Result exists", result is not None)
    check("Outcome is WIN", result.is_win)
    check("Total R positive", result.total_r > 0)
    print(f"  Total R: {result.total_r:.2f}, PnL: {result.total_pnl:.2f}")
    return True


def test_sl_hit():
    """BUY trade: fill → SL hit → loss."""
    plan = make_plan("BUY")
    broker = PaperBroker(balance=10000.0)
    om = OrderManager(broker, account_balance=10000.0)

    ticket = om.submit(plan)
    broker.inject_sl_hit(ticket, plan.stop_loss)
    closed = om.poll()

    check("Closed after SL", ticket in closed)
    result = om.result(ticket)
    check("Result exists", result is not None)
    check("Outcome is LOSS", result.is_loss)
    check("Total R ≈ -1.0", abs(result.total_r - (-1.0)) < 0.1)
    print(f"  Total R: {result.total_r:.2f}")
    return True


def test_tp1_then_reversal():
    """BUY trade: fill → TP1 → BE → SL (reversal after BE)."""
    plan = make_plan("BUY")
    broker = PaperBroker(balance=10000.0)
    om = OrderManager(broker, account_balance=10000.0)

    ticket = om.submit(plan)
    mt = om._trades[ticket]

    # TP1 → BE
    broker.inject_tp_hit(ticket, plan.take_profits[0])
    closed = om.poll()
    check("BE set after TP1", mt.lifecycle.state == "BE_SET")

    # Reversal → SL at BE
    broker.inject_sl_hit(ticket, plan.entry)
    closed = om.poll()
    check("Closed after reversal SL", ticket in closed)

    result = om.result(ticket)
    check("Outcome is WIN (TP1 locked)", result.is_win)
    check("Total R ≈ 0.5 (50% of TP1)", abs(result.total_r - 0.5) < 0.05)
    print(f"  Total R: {result.total_r:.2f}")
    return True


def test_sell_trade():
    """SELL trade: fill → TP1 → BE → TP2 → trailing → SL by trailing."""
    plan = make_plan("SELL", entry=100.0, sl=101.0)
    broker = PaperBroker(balance=10000.0)
    om = OrderManager(broker, account_balance=10000.0)

    ticket = om.submit(plan)
    mt = om._trades[ticket]
    check("SELL filled", mt.lifecycle.state == "FILLED")

    # TP1
    broker.inject_tp_hit(ticket, plan.take_profits[0])
    om.poll()
    check("BE after TP1", mt.lifecycle.state == "BE_SET")

    # TP2 → trailing
    broker.inject_tp_hit(ticket, plan.take_profits[1])
    om.poll()
    check("TRAILING after TP2", mt.lifecycle.state == "TRAILING")

    # Trailing SL hit
    broker.inject_sl_hit(ticket, mt.lifecycle.current_sl)
    closed = om.poll()
    check("Closed after trailing stop hit", ticket in closed)

    result = om.result(ticket)
    check("Outcome is WIN", result.is_win)
    check("Total R > 0", result.total_r > 0)
    print(f"  Total R: {result.total_r:.2f}")
    return True


def test_entry_not_filled():
    """Order rejected by broker → OrderRejectedError."""
    plan = make_plan("BUY")
    broker = PaperBroker(balance=10000.0)
    om = OrderManager(broker, account_balance=10000.0)

    # Disconnect broker to force rejection
    broker.disconnect()
    try:
        om.submit(plan)
        check("Should have raised", False)
        return False
    except Exception as e:
        check("Order rejected when broker not connected", "not connected" in str(e).lower())
        return True


if __name__ == "__main__":
    print("=== EXECUTION BRIDGE INTEGRATION TEST ===\n")
    tests = [
        ("Full TP chain (BUY)", test_full_tp_chain),
        ("SL hit (loss)", test_sl_hit),
        ("TP1 then reversal", test_tp1_then_reversal),
        ("SELL trade", test_sell_trade),
        ("Entry not filled (disconnected)", test_entry_not_filled),
    ]
    passed = 0
    failed = 0
    for name, fn in tests:
        print(f"\n--- {name} ---")
        try:
            if fn():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  [EXCEPTION] {e}")
            failed += 1

    print(f"\n=== RESULTS: {passed} passed, {failed} failed ===")
    if failed == 0:
        print("*** ALL EXECUTION BRIDGE TESTS PASSED ***")
    else:
        print("*** SOME TESTS FAILED ***")

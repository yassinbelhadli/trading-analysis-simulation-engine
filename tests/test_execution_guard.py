import asyncio
import sys
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

sys.path.insert(0, r"C:\Users\AGA GAMING\Desktop\test saas")

from core_engine.execution.execution_guard import ExecutionGuard, GuardResult
from core_engine.mt_runtime import (
    MTRuntimeMock, MTConnectionConfig, MTPosition, MTSymbolInfo,
)
from core_engine.engine_manager import engine_manager, EngineState
from database.models import TradingAccount, License
from config.settings import ALLOW_REAL_TRADING, DEMO_ONLY


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_config():
    return MTConnectionConfig(server="demo", login="123", password="pwd", platform="MT4")


def make_account(license_id: str | None = "lic_1", active: bool = True,
                 real_trading: bool = False) -> TradingAccount:
    acct = TradingAccount(
        id="acct_test", user_id="user_test", active=active,
        real_trading_enabled=real_trading, license_id=license_id,
    )
    acct.license_id = license_id
    return acct


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

async def run():
    ok = 0
    fail = 0
    tests_run = 0

    def check(label: str, condition: bool):
        nonlocal ok, fail, tests_run
        tests_run += 1
        if condition:
            print(f"  [OK] {label}")
            ok += 1
        else:
            print(f"  [FAIL] {label}")
            fail += 1

    # ----------------------------------------------------------------
    # 1. GuardResult basics
    # ----------------------------------------------------------------
    print("\n=== GuardResult ===")
    r1 = GuardResult(allowed=True)
    check("default empty reason", r1.reason == "")
    check("default empty warnings", r1.warnings == [])

    r2 = GuardResult(allowed=False, reason="test", warnings=["w1"])
    check("reason stored", r2.reason == "test")
    check("warnings stored", r2.warnings == ["w1"])

    # ----------------------------------------------------------------
    # 2. validate_runtime
    # ----------------------------------------------------------------
    print("\n=== validate_runtime ===")
    rt = MTRuntimeMock(make_config())
    guard = ExecutionGuard(rt, "acct_test", "user_test")

    result = guard.validate_runtime()
    check("fails when not connected", not result.allowed)
    check("reason is Runtime not connected", "not connected" in result.reason)

    await rt.connect()
    result = guard.validate_runtime()
    check("passes when connected", result.allowed)

    # ----------------------------------------------------------------
    # 3. validate_symbol
    # ----------------------------------------------------------------
    print("\n=== validate_symbol ===")
    result = await guard.validate_symbol("XAUUSD")
    check("XAUUSD found", result.allowed)

    result = await guard.validate_symbol("NAS100")
    check("NAS100 found", result.allowed)

    result = await guard.validate_symbol("FAKE_SYMBOL")
    check("fake symbol rejected", not result.allowed)
    check("reason mentions not found", "not found" in result.reason)

    # ----------------------------------------------------------------
    # 4. validate_spread
    # ----------------------------------------------------------------
    print("\n=== validate_spread ===")
    result = await guard.validate_spread("XAUUSD", max_spread=100)
    check("XAUUSD spread 25 < 100 passes", result.allowed)

    result = await guard.validate_spread("XAUUSD", max_spread=10)
    check("XAUUSD spread 25 > 10 fails", not result.allowed)
    check("reason mentions spread too high", "too high" in result.reason)

    result = await guard.validate_spread("BTCUSD", max_spread=100)
    check("BTCUSD spread 80 < 100 passes", result.allowed)

    # ----------------------------------------------------------------
    # 5. validate_market_open
    # ----------------------------------------------------------------
    print("\n=== validate_market_open ===")

    result = await guard.validate_market_open("XAUUSD")
    check("XAUUSD trade_mode=0 -> open", result.allowed)

    orig_symbols = rt._symbols.copy()
    rt._symbols["XAUUSD"] = MTSymbolInfo(
        name="XAUUSD", digits=2, spread=25,
        swap_long=-3.5, swap_short=1.2,
        min_volume=0.01, max_volume=100.0, volume_step=0.01,
        bid=2350.0, ask=2350.25, point=0.01,
        tick_value=1.0, tick_size=0.01, contract_size=100.0,
        trade_mode=1,
    )
    result = await guard.validate_market_open("XAUUSD")
    check("trade_mode=1 -> closed", not result.allowed)
    rt._symbols = orig_symbols

    # ----------------------------------------------------------------
    # 6. validate_duplicate_trade
    # ----------------------------------------------------------------
    print("\n=== validate_duplicate_trade ===")

    rt._positions.clear()
    result = await guard.validate_duplicate_trade("XAUUSD", "BUY")
    check("no positions -> passes", result.allowed)

    rt._positions.append(MTPosition(
        ticket=1001, symbol="XAUUSD", type=0, volume=0.1,
        open_price=2350.0, current_price=2351.0,
        stop_loss=2340.0, take_profit=2370.0,
        profit=10.0, swap=0.0, comment="", open_time=datetime.now(timezone.utc),
    ))
    result = await guard.validate_duplicate_trade("XAUUSD", "BUY")
    check("duplicate BUY on XAUUSD -> fails", not result.allowed)
    check("reason mentions duplicate", "Duplicate" in result.reason)

    result = await guard.validate_duplicate_trade("XAUUSD", "SELL")
    check("opposite direction -> passes", result.allowed)

    result = await guard.validate_duplicate_trade("NAS100", "BUY")
    check("different symbol -> passes", result.allowed)

    # ----------------------------------------------------------------
    # 7. validate_daily_limit
    # ----------------------------------------------------------------
    print("\n=== validate_daily_limit ===")

    result = await guard.validate_daily_limit("XAUUSD", max_trades_per_symbol=1)
    check("1 open XAUUSD buys -> limit 1 fails", not result.allowed)

    result = await guard.validate_daily_limit("XAUUSD", max_trades_per_symbol=2)
    check("1 open XAUUSD buys -> limit 2 passes", result.allowed)

    # Add more positions to test total limit
    rt._positions.append(MTPosition(
        ticket=1002, symbol="NAS100", type=0, volume=0.1,
        open_price=19500.0, current_price=19510.0,
        stop_loss=19450.0, take_profit=19600.0,
        profit=10.0, swap=0.0, comment="", open_time=datetime.now(timezone.utc),
    ))

    result = await guard.validate_daily_limit("XAUUSD", max_trades_per_symbol=2, max_trades_total=1)
    check("total limit 1 with 2 open -> fails", not result.allowed)

    result = await guard.validate_daily_limit("XAUUSD", max_trades_per_symbol=2, max_trades_total=5)
    check("total limit 5 with 2 open -> passes", result.allowed)

    rt._positions.clear()

    # ----------------------------------------------------------------
    # 8. validate_session (with no SessionManager)
    # ----------------------------------------------------------------
    print("\n=== validate_session ===")
    result = await guard.validate_session()
    check("session check passes with warning (no manager)", result.allowed)
    has_warning = any("SessionManager" in w for w in result.warnings)
    check("warning about SessionManager missing", has_warning)

    # ----------------------------------------------------------------
    # 9. validate_news
    # ----------------------------------------------------------------
    print("\n=== validate_news ===")

    result = await guard.validate_news("XAUUSD")
    check("news passes with warning (no events loaded)", result.allowed)

    # Test with a calendar that has no events
    from news_engine.calendar import EconomicCalendar
    cal = EconomicCalendar()
    result = await guard.validate_news("XAUUSD", calendar=cal)
    check("empty calendar -> passes with warning", result.allowed)

    cal.add_event(
        datetime.now(timezone.utc) + timedelta(minutes=5),
        "USD", "NonFarm Payrolls", "HIGH",
    )
    result = await guard.validate_news("XAUUSD", minutes_before=60, calendar=cal)
    check("high impact news within window -> blocks", not result.allowed)
    check("reason mentions news", "News" in result.reason)

    cal2 = EconomicCalendar()
    cal2.add_event(
        datetime.now(timezone.utc) + timedelta(minutes=90),
        "USD", "GDP", "HIGH",
    )
    result = await guard.validate_news("XAUUSD", minutes_before=30, calendar=cal2)
    check("news outside window -> passes", result.allowed)

    cal3 = EconomicCalendar()
    cal3.add_event(
        datetime.now(timezone.utc) + timedelta(minutes=5),
        "USD", "Retail Sales", "LOW",
    )
    result = await guard.validate_news("XAUUSD", minutes_before=60, calendar=cal3)
    check("LOW impact news -> passes (high_only default)", result.allowed)

    # ----------------------------------------------------------------
    # 10. validate_real_trading
    # ----------------------------------------------------------------
    print("\n=== validate_real_trading ===")

    # ALLOW_REAL_TRADING is False by default in settings
    account = make_account(real_trading=False)
    result = await guard.validate_real_trading(account)
    check("ALLOW_REAL_TRADING=False -> fails", not result.allowed)

    # ----------------------------------------------------------------
    # 11. _validate_engine
    # ----------------------------------------------------------------
    print("\n=== validate_engine ===")

    result = guard._validate_engine()
    check("engine not registered -> not running", not result.allowed)

    from core_engine.engine_manager import EngineInstance
    engine_manager._engines["acct_test"] = EngineInstance(account_id="acct_test", state=EngineState.RUNNING)
    result = guard._validate_engine()
    check("engine RUNNING -> passes", result.allowed)

    engine_manager._engines["acct_test"] = EngineInstance(account_id="acct_test", state=EngineState.PAUSED)
    result = guard._validate_engine()
    check("engine PAUSED -> fails", not result.allowed)

    engine_manager._engines["acct_test"] = EngineInstance(account_id="acct_test", state=EngineState.ERROR, error="test error")
    result = guard._validate_engine()
    check("engine ERROR -> fails", not result.allowed)

    del engine_manager._engines["acct_test"]

    # ----------------------------------------------------------------
    # 12. _validate_risk
    # ----------------------------------------------------------------
    print("\n=== validate_risk ===")

    account = make_account(active=True)
    result = await guard._validate_risk(account)
    check("active account -> passes", result.allowed)

    account.active = False
    result = await guard._validate_risk(account)
    check("inactive account -> fails", not result.allowed)
    check("reason mentions paused", "paused" in result.reason)

    # ----------------------------------------------------------------
    # 13. can_execute (combined flow)
    # ----------------------------------------------------------------
    print("\n=== can_execute (combined) ===")

    # Register a RUNNING engine so sync guards pass
    engine_manager._engines["acct_test"] = EngineInstance(account_id="acct_test", state=EngineState.RUNNING)

    with patch.object(guard, "_log_block"):
        with patch.object(guard, "_load_account", return_value=make_account()):
            with patch.object(guard, "_validate_license") as mock_lic:
                with patch.object(guard, "_validate_risk") as mock_risk:
                    mock_lic.return_value = GuardResult(allowed=True)
                    mock_risk.return_value = GuardResult(allowed=True)
                    result = await guard.can_execute()
                    check("can_execute passes when all guards pass", result.allowed)

    with patch.object(guard, "_log_block"):
        with patch.object(guard, "_load_account", return_value=make_account()):
            with patch.object(guard, "_validate_license") as mock_lic:
                mock_lic.return_value = GuardResult(allowed=False, reason="no license")
                result = await guard.can_execute()
                check("can_execute fails on license guard", not result.allowed)
                check("reason is from failing guard", "no license" in result.reason)

    del engine_manager._engines["acct_test"]

    # ----------------------------------------------------------------
    # 14. full_checklist
    # ----------------------------------------------------------------
    print("\n=== full_checklist ===")

    with patch.object(guard, "_load_account", return_value=None):
        checklist = await guard.full_checklist("XAUUSD", "BUY")
        check("no account -> returns account fail", "account" in checklist)
        check("account result is fail", not checklist["account"].allowed)

    with patch.object(guard, "_log_block"):
        with patch.object(guard, "_load_account", return_value=make_account()):
            with patch.object(guard, "_validate_license") as mock_lic:
                mock_lic.return_value = GuardResult(allowed=True, warnings=[], reason="")
                checklist = await guard.full_checklist(
                    "XAUUSD", "BUY", account=make_account(),
                )
            expected_keys = {
                "runtime", "engine", "license", "risk", "symbol",
                "spread", "market_open", "news", "duplicate",
                "daily_limit", "session", "real_trading",
            }
            check("all 12 checks in checklist", expected_keys == set(checklist.keys()))
            for key in expected_keys:
                check(f"  - {key} is GuardResult", isinstance(checklist[key], GuardResult))

    # ----------------------------------------------------------------
    # 15. _validate_license (with mocked repos)
    # ----------------------------------------------------------------
    print("\n=== validate_license (with mock DB) ===")

    lic_active = License(id="lic_1", status="active",
                         expires_at=datetime.now(timezone.utc) + timedelta(days=30))

    with patch("core_engine.execution.execution_guard.async_session_factory") as mock_sf:
        mock_session = AsyncMock()
        mock_sf.return_value.__aenter__.return_value = mock_session
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=lic_active)
        mock_session.get.return_value = lic_active

        with patch("core_engine.execution.execution_guard.LicenseRepository",
                   return_value=mock_repo):
            account = make_account(license_id="lic_1")
            result = await guard._validate_license(account)
            check("active license -> passes", result.allowed)

    lic_inactive = License(id="lic_1", status="inactive",
                           expires_at=datetime.now(timezone.utc) + timedelta(days=30))
    with patch("core_engine.execution.execution_guard.async_session_factory") as mock_sf:
        mock_session = AsyncMock()
        mock_sf.return_value.__aenter__.return_value = mock_session
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=lic_inactive)
        with patch("core_engine.execution.execution_guard.LicenseRepository",
                   return_value=mock_repo):
            account = make_account(license_id="lic_1")
            result = await guard._validate_license(account)
            check("inactive license -> fails", not result.allowed)
            check("reason mentions status", "inactive" in result.reason or "status" in result.reason)

    lic_expired = License(id="lic_1", status="active",
                          expires_at=datetime.now(timezone.utc) - timedelta(days=1))
    with patch("core_engine.execution.execution_guard.async_session_factory") as mock_sf:
        mock_session = AsyncMock()
        mock_sf.return_value.__aenter__.return_value = mock_session
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=lic_expired)
        with patch("core_engine.execution.execution_guard.LicenseRepository",
                   return_value=mock_repo):
            account = make_account(license_id="lic_1")
            result = await guard._validate_license(account)
            check("expired license -> fails", not result.allowed)
            check("reason mentions expired", "expired" in result.reason)

    # ----------------------------------------------------------------
    # 16. Edge: DB load fails gracefully
    # ----------------------------------------------------------------
    print("\n=== Edge cases ===")
    with patch.object(guard, "_log_block"):
        with patch.object(guard, "_load_account", return_value=None):
            result = await guard.can_execute()
            check("can_execute with no account -> fails", not result.allowed)
            check("reason mentions not found", "not found" in result.reason)

    with patch.object(guard, "_log_block"):
        with patch.object(guard, "_load_account", return_value=make_account()):
            with patch.object(guard, "_validate_license",
                              side_effect=Exception("DB crash")):
                result = await guard.can_execute()
                check("license check exception caught", not result.allowed)

    # ----------------------------------------------------------------
    # 17. Position type direction mapping
    # ----------------------------------------------------------------
    print("\n=== Position type direction ===")
    rt._positions.clear()
    for pos_type, expected_dir in [(0, "BUY"), (1, "SELL"), (2, "BUY"), (3, "SELL"),
                                   (4, "BUY"), (5, "SELL")]:
        rt._positions.append(MTPosition(
            ticket=2000 + pos_type, symbol="XAUUSD", type=pos_type, volume=0.1,
            open_price=2350.0, current_price=2351.0,
            stop_loss=2340.0, take_profit=2370.0,
            profit=10.0, swap=0.0, comment="", open_time=datetime.now(timezone.utc),
        ))
        result = await guard.validate_duplicate_trade("XAUUSD", expected_dir)
        check(f"type={pos_type} direction={expected_dir} -> duplicate detected", not result.allowed)
        rt._positions.clear()

    # ----------------------------------------------------------------
    # Summary
    # ----------------------------------------------------------------
    print(f"\n{'='*50}")
    print(f"RESULTS: {ok} OK / {fail} FAIL / {tests_run} TOTAL")
    print(f"{'='*50}")

    if fail == 0:
        print("*** EXECUTION GUARD TESTS PASSED ***")
    else:
        print("*** EXECUTION GUARD TESTS FAILED ***")

    return fail == 0


if __name__ == "__main__":
    success = asyncio.run(run())
    sys.exit(0 if success else 1)

"""
Pre-flight Check — run before launching demo validation.

Usage:
    python backtester/preflight_check.py

Checks:
    1. MT5 Connection (with 15s timeout)
    2. config.settings
    3. Runtime components
    4. Symbols
    5. Validation Paths

Exits with 0 if all checks pass, 1 otherwise.
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

PASS = 0
FAIL = 0
WARN = 0
SKIP = 0


def ok(msg: str):
    global PASS
    PASS += 1
    print(f"  [PASS] {msg}")


def fail(msg: str):
    global FAIL
    FAIL += 1
    print(f"  [FAIL] {msg}")


def warn(msg: str):
    global WARN
    WARN += 1
    print(f"  [WARN] {msg}")


def skip(msg: str):
    global SKIP
    SKIP += 1
    print(f"  [SKIP] {msg}")


print("=" * 70)
print("PRE-FLIGHT CHECK — Demo Forward Validation")
print("=" * 70)

# ──────────────────────────────────────────
# 1. MT5 Connection
# ──────────────────────────────────────────
print("\n--- 1. MT5 Connection ---")

mt5_path = Path(r"C:\Program Files\MetaTrader 5\terminal64.exe")
if mt5_path.exists():
    ok(f"MT5 terminal found: {mt5_path}")
else:
    warn("MT5 terminal not found at default path (may be headless/container)")

try:
    import MetaTrader5 as mt5
    ok("MetaTrader5 Python package installed")

    initialized = False
    t0 = time.time()
    try:
        initialized = mt5.initialize(timeout=15000)
    except Exception as e:
        fail(f"MT5 initialize() raised: {e}")

    if initialized:
        ok(f"MT5 initialize() OK ({time.time()-t0:.1f}s)")

        terminal = mt5.terminal_info()
        if terminal:
            ok(f"Terminal: {terminal.name} | connected={terminal.connected}")
        else:
            warn("terminal_info() returned None")

        account = mt5.account_info()
        if account is not None:
            ok(f"Account: login={account.login} balance={account.balance} "
               f"{account.currency} leverage=1:{account.leverage}")
            if account.trade_mode == 0:
                ok("trade_mode=DEMO")
            elif account.trade_mode == 1:
                fail("trade_mode=1 (REAL) — DEMO_ONLY mode, but connected to REAL!")
            else:
                warn(f"trade_mode={account.trade_mode} (unknown)")

            info_connected = terminal and terminal.connected if terminal else False
            if info_connected:
                ok("Terminal connected = True")
            else:
                fail("Terminal connected = False")

            if account.trade_allowed:
                ok("trade_allowed = True")
            else:
                fail("trade_allowed = False")
        else:
            fail("account_info() returned None — not logged in")

        if account:
            print(f"     Server: {account.server}")
            print(f"     Company: {account.company}")
            print(f"     Name: {account.name}")
            print(f"     Balance: {account.balance} | Equity: {account.equity} | "
                  f"Margin: {account.margin} | Free: {account.margin_free}")

        mt5.shutdown()
    else:
        error = mt5.last_error()
        fail(f"MT5 initialize() failed: {error} ({time.time()-t0:.1f}s)")
        warn("MT5 terminal may not be open or configured. Check MT5 login.")

except ImportError:
    warn("MetaTrader5 Python package not installed")
    skip("MT5 checks — package not available")

# ──────────────────────────────────────────
# 2. config.settings
# ──────────────────────────────────────────
print("\n--- 2. config.settings ---")

try:
    from config.settings import (
        DEMO_ONLY, ALLOW_REAL_TRADING, TELEGRAM_BOT_TOKEN,
        NEWS_PROVIDER, BASE_DIR,
    )
    ok("config.settings imported")

    if DEMO_ONLY:
        ok("DEMO_ONLY = True")
    else:
        fail("DEMO_ONLY = False — real trading enabled!")

    if not ALLOW_REAL_TRADING:
        ok("ALLOW_REAL_TRADING = False")
    else:
        fail("ALLOW_REAL_TRADING = True — risk of real trade!")

    if TELEGRAM_BOT_TOKEN and "YOUR_" not in TELEGRAM_BOT_TOKEN:
        ok(f"TELEGRAM_BOT_TOKEN set ({TELEGRAM_BOT_TOKEN[:10]}...)")
    else:
        fail("TELEGRAM_BOT_TOKEN not set or still default")

    print(f"     NEWS_PROVIDER = {NEWS_PROVIDER}")
    print(f"     BASE_DIR = {BASE_DIR}")

    try:
        from core_engine.config.trading_modes import TRADING_MODES
        for mode in ["ULTRA_CONSERVATIVE", "CONSERVATIVE", "BALANCED", "AGGRESSIVE"]:
            if mode in TRADING_MODES:
                ok(f"Trading mode '{mode}' configured")
            else:
                fail(f"Trading mode '{mode}' missing from TRADING_MODES")
    except Exception as e:
        warn(f"Trading modes check: {e}")

except Exception as e:
    fail(f"config.settings error: {e}")

# ──────────────────────────────────────────
# 3. Runtime Components
# ──────────────────────────────────────────
print("\n--- 3. Runtime Components ---")

components = [
    ("Scanner", "core_engine.scanner", "account_scanner"),
    ("EngineRunner", "core_engine.engine_runner", "engine_runner"),
    ("HealthMonitor", "core_engine.health.health_monitor", "health_monitor"),
    ("ValidationHarness", "core_engine.validation.harness", "harness"),
    ("SetupDetector", "core_engine.detection.setup_detector", "SetupDetector"),
    ("TradePlanner", "core_engine.execution.trade_planner", "TradePlanner"),
    ("ExecutionEngine", "core_engine.execution.execution_engine", "ExecutionEngine"),
    ("PaperTrading", "core_engine.execution.paper_trading", "paper_trading"),
    ("OrderManager", "core_engine.execution.order_manager", "OrderManager"),
    ("TradeManager", "core_engine.execution.trade_manager", "TradeManager"),
]

for label, module, attr in components:
    try:
        __import__(module, fromlist=[attr])
        ok(f"{label} module loaded")
    except Exception as e:
        warn(f"{label} module: {e}")

# ──────────────────────────────────────────
# 4. Symbols (info only — actual check requires MT5)
# ──────────────────────────────────────────
print("\n--- 4. Symbols ---")

SYMBOLS_TO_CHECK = {
    "XAUUSD": ["XAUUSD", "XAUUSD.cash", "XAUUSD.n"],
    "NAS100": ["NAS100", "US100.cash", "US100", "USTEC", "USTEC.cash"],
    "BTCUSD": ["BTCUSD", "BTCUSD.cash", "XBTUSD"],
}
try:
    from core_engine.risk.symbol_validator import SymbolValidator
    normalizer = SymbolValidator()

    import MetaTrader5 as mt5
    init = mt5.initialize(timeout=10000)
    if init:
        for norm_name, aliases in SYMBOLS_TO_CHECK.items():
            found = None
            for alias in aliases:
                info = mt5.symbol_info(alias)
                if info is not None:
                    found = alias
                    mt5.symbol_select(alias, True)
                    info = mt5.symbol_info(alias)
                    mode_str = {0: "FULL", 1: "DISABLED", 2: "LONG_ONLY", 3: "SHORT_ONLY"}.get(info.trade_mode, f"MODE_{info.trade_mode}")
                    ok(f"{norm_name} -> {alias}: spread={info.spread} digits={info.digits} "
                       f"trade_mode={mode_str} visible={info.visible}")
                    break
                else:
                    mt5.symbol_select(alias, True)
                    info2 = mt5.symbol_info(alias)
                    if info2 is not None:
                        found = alias
                        mode_str = {0: "FULL", 1: "DISABLED", 2: "LONG_ONLY", 3: "SHORT_ONLY"}.get(info2.trade_mode, f"MODE_{info2.trade_mode}")
                        ok(f"{norm_name} -> {alias} (after select): spread={info2.spread} "
                           f"trade_mode={mode_str}")
                        break
            if found is None:
                warn(f"{norm_name}: no alias found — check broker symbol list")
        mt5.shutdown()
    else:
        mt5.shutdown()
        warn("MT5 not available — cannot check symbols live")
        skip("Symbol checks")
except ImportError:
    warn("MetaTrader5 not installed — cannot check symbols")
    skip("Symbol checks")

# ──────────────────────────────────────────
# 5. Validation Paths
# ──────────────────────────────────────────
print("\n--- 5. Validation Paths ---")

paths = ["data/validation", "data/validation/replay", "data/logs"]
for p in paths:
    fp = ROOT / p
    try:
        fp.mkdir(parents=True, exist_ok=True)
        test_file = fp / ".write_test"
        test_file.write_text("ok")
        test_file.unlink()
        ok(f"{p}/ — writable")
    except Exception as e:
        fail(f"{p}/ — cannot write: {e}")

# ──────────────────────────────────────────
# Summary
# ──────────────────────────────────────────
print("\n" + "=" * 70)
total = PASS + FAIL + WARN + SKIP
print(f"RESULTS: {PASS} passed | {FAIL} failed | {WARN} warnings | {SKIP} skipped")
print("=" * 70)

if FAIL > 0:
    print(f"\n{WARN} warnings, {FAIL} failures found.")
    print("Fix failures before launching demo validation.")
    sys.exit(1)
elif WARN > 4:
    print(f"\n{WARN} warnings — review before proceeding.")
    sys.exit(0)
else:
    print("\n[READY] All critical checks pass! Launch demo validation:")
    print(f"    cd {ROOT}")
    print("    python -m backtester.demo_validation")
    print()
    sys.exit(0)

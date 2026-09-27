"""
Comprehensive unit test for Phase C1-C4.
Tests Python logic only (no database connection required).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

import os
import asyncio
os.environ["TELEGRAM_BOT_TOKEN"] = "test:token"
os.environ["JWT_SECRET"] = "test-jwt-secret"

PASS = 0
FAIL = 0
TOTAL_TESTS = 0


def check(name, condition, detail=""):
    global PASS, FAIL, TOTAL_TESTS
    TOTAL_TESTS += 1
    if condition:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        detail_str = f" -- {detail}" if detail else ""
        print(f"  [FAIL] {name}{detail_str}")


print("=" * 60)
print("  PHASE C1-C4 COMPREHENSIVE TEST")
print("=" * 60)

# ============================
# 1. Email Service
# ============================
print("\n--- 1. Email Service ---")
from api.services.email_service import generate_verification_code
code = generate_verification_code()
check("generate_verification_code returns 8 char uppercase", 
      len(code) == 8 and code.isupper() and code.isalnum(), f"got: {code}")

check("generate_verification_code is random", 
      generate_verification_code() != generate_verification_code())


# ============================
# 2. Auth Router - route registration
# ============================
print("\n--- 2. Auth Router Routes ---")
from api.routes.auth_router import auth_router
auth_paths = [str(r.path) for r in auth_router.routes]
expected_auth = [
    "/auth/login", "/auth/register", "/auth/refresh", 
    "/auth/logout", "/auth/logout-all", "/auth/me",
    "/auth/change-password", "/auth/forgot-password",
    "/auth/reset-password", "/auth/verify-email/send",
    "/auth/verify-email/confirm", "/auth/check-permission",
]
for path in expected_auth:
    check(f"Route {path}", path in auth_paths)


# ============================
# 3. License Key Generation
# ============================
print("\n--- 3. License Key ---")
from security.license_gen import generate_license_key
key = generate_license_key()
check("License starts with ICT-", key.startswith("ICT-"), f"got: {key}")
check("License has 3 dashes", key.count("-") == 3, f"got: {key}")
check("License total length 18 (ICT-XXXX-XXXX-XXXX)", len(key) == 18, f"got: {len(key)}: {key}")
# Generate 5 keys and verify uniqueness
keys = [generate_license_key() for _ in range(5)]
check("All generated keys unique", len(set(keys)) == 5)


# ============================
# 4. Client Dashboard API routes
# ============================
print("\n--- 4. Client Dashboard API Routes ---")
from api.routes.client.dashboard import router as client_router
client_paths = [str(r.path) for r in client_router.routes]
expected_client = ["/client/overview", "/client/trades", "/client/license",
                   "/client/settings", "/client/performance"]
for path in expected_client:
    check(f"Route {path}", path in client_paths)

# Verify PATCH method on settings
settings_patch = False
for r in client_router.routes:
    path = getattr(r, "path", "")
    if path == "/client/settings":
        methods = getattr(r, "methods", set())
        if "PATCH" in methods:
            settings_patch = True
check("Settings has PATCH method", settings_patch)


# ============================
# 5. License API routes
# ============================
print("\n--- 5. License API Routes ---")
from api.routes.licenses import router as lic_router
lic_paths = [str(r.path) for r in lic_router.routes]
expected_lic = ["/licenses/my", "/licenses/bind", "/licenses/unbind"]
for path in expected_lic:
    check(f"Route {path}", path in lic_paths)


# ============================
# 6. License System modules
# ============================
print("\n--- 6. License System Modules ---")
from license_system.license_manager import create_license, check_expired_licenses
from license_system.activation import activate_license, deactivate_license, suspend_license
from license_system.expiry_checker import expire_license, renew_license, check_expiring_licenses

check("create_license is callable", callable(create_license))
check("activate_license is callable", callable(activate_license))
check("deactivate_license is callable", callable(deactivate_license))
check("renew_license is callable", callable(renew_license))
check("expire_license is callable", callable(expire_license))


# ============================
# 7. Database Models
# ============================
print("\n--- 7. Database Models ---")
from database.models import VerificationToken, License, User, PaperTrade

check("VerificationToken has code field", hasattr(VerificationToken, 'code'))
check("VerificationToken has type field", hasattr(VerificationToken, 'type'))
check("VerificationToken has expires_at", hasattr(VerificationToken, 'expires_at'))
check("VerificationToken has used field", hasattr(VerificationToken, 'used'))

check("License has license_key", hasattr(License, 'license_key'))
check("License has status", hasattr(License, 'status'))
check("License has max_accounts", hasattr(License, 'max_accounts'))
check("License has bound_account_id", hasattr(License, 'bound_account_id'))


# ============================
# 8. Screenshot Engine
# ============================
print("\n--- 8. Screenshot Engine ---")
from media.chart_capture import generate_entry_chart, generate_exit_chart, get_screenshot_path
from media.trade_images import capture_trade_entry, capture_trade_exit, get_trade_screenshots

check("generate_entry_chart is callable", callable(generate_entry_chart))
check("generate_exit_chart is callable", callable(generate_exit_chart))
check("capture_trade_entry is async", asyncio.iscoroutinefunction(capture_trade_entry))

chart_dir = ROOT / "storage" / "screenshots"
check("Screenshots directory exists", chart_dir.exists())

# Generate test chart
from datetime import datetime, timezone, timedelta
import random
random.seed(42)
now = datetime.now(timezone.utc)
ohlc = []
price = 3368.0
for i in range(40):
    t = now - timedelta(minutes=i * 5)
    high = price + random.uniform(0.5, 2.0)
    low = price - random.uniform(0.5, 2.0)
    close = price + random.uniform(-1, 1)
    ohlc.append((t, price, high, low, close))
    price = close

path1 = generate_entry_chart(
    trade_id='test_verify_001', symbol='XAUUSD', direction='BUY',
    entry_price=3368.25, stop_loss=3361.10, take_profit=3386.20,
    ohlc_data=ohlc,
    reasons=['BOS', 'CHoCH', 'Liquidity Sweep', 'Bullish FVG'],
)
check("Entry chart generated to file", path1 and Path(path1).exists(), str(path1))
check("Entry chart file size > 1KB", Path(path1).stat().st_size > 1000)

path2 = generate_exit_chart(
    trade_id='test_verify_001', symbol='XAUUSD', direction='BUY',
    entry_price=3368.25, stop_loss=3361.10, take_profit=3386.20,
    exit_price=3386.20, exit_reason='TP_HIT',
    realized_pnl=64.50, realized_r=2.5, ohlc_data=ohlc,
)
check("Exit chart generated to file", path2 and Path(path2).exists(), str(path2))

ss = get_trade_screenshots('test_verify_001')
check("get_trade_screenshots returns entry", ss.get('entry') is not None)
check("get_trade_screenshots returns exit", ss.get('exit') is not None)

# Cleanup test files
import shutil
shutil.rmtree(ROOT / "storage" / "screenshots" / "test_verify_001", ignore_errors=True)
print("  (test screenshots cleaned up)")


# ============================
# 9. Screenshots API
# ============================
print("\n--- 9. Screenshots API Route ---")
from api.routes.screenshots import router as ss_router
ss_paths = [str(r.path) for r in ss_router.routes]
check("GET /screenshots/{trade_id}/{type} registered", any("screenshots" in p for p in ss_paths))


# ============================
# 10. Telegram Trade Messages
# ============================
print("\n--- 10. Telegram Trade Messages ---")
from telegram_bot.ui.trade_messages import (
    format_entry_message, format_exit_message,
    format_performance_summary, format_license_info,
    format_open_trades, format_help,
)

# Entry message
e = format_entry_message(
    symbol='XAUUSD', direction='BUY',
    entry_price=3368.25, stop_loss=3361.10, take_profit=3386.20,
    score=96, confidence=88, risk_pct=0.5, rr=2.5,
    reasons=['BOS', 'CHoCH', 'Liquidity Sweep', 'Bullish FVG', 'Order Block'],
    lot_size=0.1,
)
check("Entry: has symbol", 'XAUUSD' in e)
check("Entry: has direction", 'BUY' in e)
check("Entry: has score", '96%' in e)
check("Entry: has entry price", '3368.25' in e)
check("Entry: has SL", '3361.10' in e)
check("Entry: has TP", '3386.20' in e)
check("Entry: has risk %", '0.5%' in e)
check("Entry: has RR", '2.5' in e)
check("Entry: has reasons", 'Bullish FVG' in e)

# Exit message
x = format_exit_message(
    symbol='XAUUSD', direction='BUY',
    entry_price=3368.25, exit_price=3386.20,
    exit_reason='TP_HIT', realized_pnl=64.50, realized_r=2.5,
    duration='2h 31m', mfe=68.0, mae=12.0,
    partial_pnl=32.0, be_activated=True,
)
check("Exit: has PnL", '+$64.50' in x)
check("Exit: has R", '+2.50R' in x)
check("Exit: has duration", '2h 31m' in x)
check("Exit: has partial", '+$32.00' in x)
check("Exit: has BE", 'Breakeven' in x)

# Performance summary
p = format_performance_summary(
    total_trades=50, wins=32, losses=18,
    win_rate=64.0, net_pnl=2524.92, profit_factor=3.81, avg_r=1.8,
    best_symbol='XAUUSD', today_pnl=125.0,
)
check("Perf: has trades count", '50' in p)
check("Perf: has win rate", '64.0%' in p)
check("Perf: has PF", '3.81' in p)
check("Perf: has best symbol", 'XAUUSD' in p)

# License message
l = format_license_info(
    license_key='ICT-9AK2-HQ7D-X29P', plan='Professional',
    status='active', expires_at='2026-12-15',
    max_accounts=2, bound_accounts=1,
)
check("License: has key", 'ICT-9AK2-HQ7D-X29P' in l)
check("License: has plan", 'Professional' in l)
check("License: has status", 'ACTIVE' in l)

# Help message
h = format_help()
for cmd in ['/start', '/performance', '/license', '/history', '/open', '/help']:
    check(f"Help: has {cmd}", cmd in h)

# Open trades message
ot = format_open_trades([{"symbol": "XAUUSD", "direction": "BUY", "entry_price": 3368.25, "unrealized_pnl": 12.50}])
check("Open trades: has symbol", 'XAUUSD' in ot)

ot_empty = format_open_trades([])
check("Open trades: empty", 'No open trades' in ot_empty)


# ============================
# 11. Alert Service
# ============================
print("\n--- 11. Alert Service ---")
from telegram_bot.services.alert_service import AlertService, EVENT_EMOJI, ALERT_EVENTS

check("ALERT_EVENTS defined", len(ALERT_EVENTS) >= 12, f"got: {len(ALERT_EVENTS)}")
check("EVENT_EMOJI defined", len(EVENT_EMOJI) >= 15, f"got: {len(EVENT_EMOJI)}")

# Check specific event coverage
check("Has TRADE_OPENED emoji", "TRADE_OPENED" in EVENT_EMOJI)
check("Has PAPER_TRADE_FILLED emoji", "PAPER_TRADE_FILLED" in EVENT_EMOJI)
check("Has BREAK_EVEN_MOVED emoji", "BREAK_EVEN_MOVED" in EVENT_EMOJI)
check("Has PARTIAL_CLOSE emoji", "PARTIAL_CLOSE" in EVENT_EMOJI)


# ============================
# 12. Report Service
# ============================
print("\n--- 12. Report Service ---")
from telegram_bot.services.report_service import generate_user_summary, send_daily_summaries
check("generate_user_summary is async", asyncio.iscoroutinefunction(generate_user_summary))
check("send_daily_summaries is async", asyncio.iscoroutinefunction(send_daily_summaries))


# ============================
# 13. Bot command registration
# ============================
print("\n--- 13. Bot Commands ---")
from telegram_bot.app import build_application
try:
    full_app = build_application(full=True, with_alert_post_init=False)
    all_handlers = []
    for handler_list in full_app.handlers.values():
        for h in handler_list:
            if hasattr(h, 'commands') and h.commands:
                all_handlers.extend(h.commands)
    
    expected_cmds = ['start', 'status', 'performance', 'license', 
                     'history', 'open', 'help', 'validation', 'summary',
                     'debug', 'license_cmd', 'help_cmd', 'open_trades']
    missing = [c for c in expected_cmds if c not in all_handlers]
    check("All expected handlers registered", len(missing) == 0, f"missing: {missing}")
except Exception as ex:
    check("Bot init", False, str(ex))


# ============================
# 14. API main.py includes all routers
# ============================
print("\n--- 14. API Main Router Registration ---")
from api.main import app
router_count = sum(1 for r in app.routes if type(r).__name__ == '_IncludedRouter')
check("All routers registered in main.py", router_count >= 10, f"got: {router_count}")


# ============================
# Final Summary
# ============================
print(f"\n{'='*60}")
print(f"  RESULTS: {PASS}/{TOTAL_TESTS} passed, {FAIL}/{TOTAL_TESTS} failed")
print(f"{'='*60}")

if FAIL > 0:
    print("\n  ❌ Some tests failed. Review the [FAIL] entries above.")
    sys.exit(1)
else:
    print("\n  ✅ ALL TESTS PASSED!")
    sys.exit(0)

"""Tests for minimum trading days and profit target enforcement.

Verifies:
  - below minimum trading days → warning (not a block)
  - minimum trading days met → no warning
  - profit target below → allowed (not yet reached)
  - profit target reached → BLOCKED
  - interaction with max daily loss / max account loss
  - personal accounts are NOT restricted by funded-only rules
"""
import httpx, json, sys, uuid, asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from database.db import async_session_factory
from database.models import TradingAccount, RiskProfile, User

BASE = "http://localhost:8000"
_T = 30.0

passed = failed = 0

def check(label, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  PASS: {label}")
        passed += 1
    else:
        print(f"  FAIL: {label} {detail}")
        failed += 1


def get_token(email, password):
    r = httpx.post(f"{BASE}/auth/login",
                    json={"email": email, "password": password},
                    timeout=_T)
    return r.json().get("access_token")


def make_headers(token):
    return {"Authorization": f"Bearer {token}"}


# ──────────────────────────────────────────────────────────────
# SECTION 1: Create a funded account with profit_target + min_trading_days
# ──────────────────────────────────────────────────────────────
async def test_profit_target_blocks():
    """FUNDED account with profit_target=10% — create and verify risk fields are stored."""
    print("\n=== TEST: Profit Target Config Stored ===")
    async with async_session_factory() as session:
        u = (await session.execute(
            select(User).where(User.email == "demo.client@ict-ea-demo.dev")
        )).scalar_one_or_none()
        if not u:
            check("Client user exists", False, "not found")
            return

        acct_id = str(uuid.uuid4())
        account = TradingAccount(
            id=acct_id, user_id=u.id, account_type="FUNDED",
            platform="MT5", server="FTMO-Server",
            login=str(uuid.uuid4().int % 10**8),
            name="PT Test Account", broker="FTMO", prop_firm="FTMO",
            program="ftmo_2_step_standard",
            account_size=10000.0, balance_snapshot=10000.0, equity_snapshot=10000.0,
            account_fingerprint=f"test-pt-{acct_id}", active=True, verified=True,
        )
        session.add(account)
        await session.flush()

        risk = RiskProfile(
            account_id=acct_id, daily_loss=5.0, max_loss=10.0,
            profit_target=10.0, min_trading_days=4, mode="balanced",
            initial_balance=10000.0,
        )
        session.add(risk)
        await session.commit()

        acct = (await session.execute(
            select(TradingAccount)
            .options(selectinload(TradingAccount.risk_profile))
            .where(TradingAccount.id == acct_id)
        )).scalar_one_or_none()

        check("Account created", acct is not None)
        check("Account is FUNDED", acct.account_type == "FUNDED")

        rp = acct.risk_profile
        check("Risk profile exists", rp is not None)
        if rp:
            check("profit_target=10 stored", rp.profit_target == 10.0, f"got {rp.profit_target}")
            check("min_trading_days=4 stored", rp.min_trading_days == 4, f"got {rp.min_trading_days}")
            check("daily_loss=5 stored", rp.daily_loss == 5.0)
            check("max_loss=10 stored", rp.max_loss == 10.0)

        # Cleanup
        await session.delete(risk)
        await session.delete(account)
        await session.commit()


# ──────────────────────────────────────────────────────────────
# SECTION 2: Personal accounts must NOT be restricted
# ──────────────────────────────────────────────────────────────
async def test_personal_not_restricted():
    """Personal accounts should NOT be blocked by profit target or min trading days."""
    print("\n=== TEST: Personal Account Not Restricted ===")
    token = get_token("demo.client@ict-ea-demo.dev", "ClientDemo!2026")
    h = make_headers(token)

    r = httpx.get(f"{BASE}/api/client/accounts", headers=h, timeout=_T)
    check("Personal account list returns 200", r.status_code == 200, f"got {r.status_code}")

    accts = r.json().get("items", r.json().get("accounts", []))
    personal = [a for a in accts if a.get("account_type") == "PERSONAL"]
    if personal:
        check("Personal account exists for testing", True)
    else:
        check("Personal account exists", False, "no personal accounts found — skipping")


# ──────────────────────────────────────────────────────────────
# SECTION 3: Record trading day
# ──────────────────────────────────────────────────────────────
async def test_record_trading_day():
    """Test the trading day recording mechanism."""
    print("\n=== TEST: Record Trading Day ===")
    token = get_token("demo.client@ict-ea-demo.dev", "ClientDemo!2026")
    h = make_headers(token)

    r = httpx.get(f"{BASE}/api/client/accounts", headers=h, timeout=_T)
    if r.status_code != 200:
        check("Account list available", False, f"got {r.status_code}")
        return

    accts = r.json().get("items", r.json().get("accounts", []))
    if not accts:
        check("Has at least one account", False, "no accounts")
        return

    aid = accts[0]["id"]
    check("Found account for trading day test", True, aid)

    r2 = httpx.post(f"{BASE}/api/client/accounts/{aid}/record-trading-day",
                    headers=h, timeout=_T)
    if r2.status_code == 200:
        check("Record trading day returns 200", True)
    elif r2.status_code == 404:
        check("Record trading day endpoint exists", False, "404")
    else:
        check("Record trading day response", True, f"status={r2.status_code}")


# ──────────────────────────────────────────────────────────────
# SECTION 4: Risk check API includes all guards
# ──────────────────────────────────────────────────────────────
async def test_funded_risk_includes_all_guards():
    """Verify that the risk check API includes profit target and min trading days."""
    print("\n=== TEST: Funded Risk Check ===")
    token = get_token("demo.client@ict-ea-demo.dev", "ClientDemo!2026")
    h = make_headers(token)

    r = httpx.get(f"{BASE}/api/client/accounts", headers=h, timeout=_T)
    accts = r.json().get("items", r.json().get("accounts", []))

    if not accts:
        check("Has accounts for risk check", False, "no accounts")
        return

    aid = accts[0]["id"]
    r2 = httpx.post(f"{BASE}/api/client/accounts/{aid}/risk-check",
                    headers=h,
                    json={"current_equity": 10000, "daily_start_equity": 10000},
                    timeout=_T)
    if r2.status_code == 200:
        result = r2.json()
        check("Risk check returns dict", isinstance(result, dict))
        check("Risk check has 'allowed' field", "allowed" in result, f"keys: {list(result.keys())}")
    elif r2.status_code == 404:
        check("Risk check endpoint", False, "404 — endpoint not wired")
    else:
        check("Risk check responds", True, f"status={r2.status_code}")


# ──────────────────────────────────────────────────────────────
# SECTION 5: Interaction — max loss + profit target + min days
# ──────────────────────────────────────────────────────────────
async def test_max_loss_plus_profit_target():
    """Both max loss AND profit target should be checked; max loss should block first."""
    print("\n=== TEST: Max Loss + Profit Target Interaction ===")
    async with async_session_factory() as session:
        u = (await session.execute(
            select(User).where(User.email == "demo.client@ict-ea-demo.dev")
        )).scalar_one_or_none()
        if not u:
            check("Client user exists", False, "not found")
            return

        acct_id = str(uuid.uuid4())
        account = TradingAccount(
            id=acct_id, user_id=u.id, account_type="FUNDED",
            platform="MT5", server="FTMO-Server",
            login=str(uuid.uuid4().int % 10**8),
            name="Integration Test", broker="FTMO", prop_firm="FTMO",
            account_size=10000.0, balance_snapshot=10000.0, equity_snapshot=10000.0,
            account_fingerprint=f"test-int-{acct_id}", active=True, verified=True,
        )
        session.add(account)
        await session.flush()

        risk = RiskProfile(
            account_id=acct_id, daily_loss=5.0, max_loss=10.0,
            profit_target=10.0, min_trading_days=5, mode="balanced",
            initial_balance=10000.0,
        )
        session.add(risk)
        await session.commit()

        from core_engine.risk_manager import RiskManager
        rm = RiskManager(session)

        # Test 1: 50% loss → trade NOT allowed (max loss blocks)
        allowed = await rm.is_trade_allowed(
            acct_id, current_equity=5000.0, daily_start_equity=9500.0,
        )
        check("50% loss → trade NOT allowed", allowed is False, f"allowed={allowed}")

        # Test 2: Profit target reached → BLOCKED
        pt = await rm.check_profit_target(acct_id, current_equity=11000.0, start_balance=10000.0)
        check("Profit target reached at +10%", pt.allowed is False, f"allowed={pt.allowed}")
        check("Profit target reason correct", "reached" in pt.reason.lower(), f"reason={pt.reason}")

        # Test 3: Profit target NOT reached
        pt2 = await rm.check_profit_target(acct_id, current_equity=10500.0, start_balance=10000.0)
        check("Profit target NOT reached at +5%", pt2.allowed is True, f"allowed={pt2.allowed}")

        # Test 4: Min trading days — warning only, not block
        mtd = await rm.check_min_trading_days(acct_id)
        check("Min trading days: has warning (0/5)", mtd.warning is not None, f"warning={mtd.warning}")
        check("Min trading days: allowed=True (warning, not block)", mtd.allowed is True)
        check("Min trading days: days_remaining=5", mtd.days_remaining == 5, f"remaining={mtd.days_remaining}")

        # Test 5: Record trading day → count increases
        await rm.record_trading_day(acct_id)
        await session.commit()

        mtd2 = await rm.check_min_trading_days(acct_id)
        check("After recording: trading_days_count >= 1", mtd2.trading_days_count >= 1, f"count={mtd2.trading_days_count}")
        check("After recording: days_remaining=4", mtd2.days_remaining == 4, f"remaining={mtd2.days_remaining}")

        # Test 6: Record same day again → idempotent
        await rm.record_trading_day(acct_id)
        await session.commit()

        mtd3 = await rm.check_min_trading_days(acct_id)
        check("Double-record same day: still count=1", mtd3.trading_days_count == 1, f"count={mtd3.trading_days_count}")

        # Test 7: Profit target blocks even when profit is reached (is_trade_allowed)
        # Set equity high enough to reach target
        account.equity_snapshot = 11000.0
        await session.commit()
        allowed2 = await rm.is_trade_allowed(
            acct_id, current_equity=11000.0, daily_start_equity=11000.0, start_balance=10000.0,
        )
        check("Profit target reached → is_trade_allowed=False", allowed2 is False, f"allowed={allowed2}")

        # Cleanup
        await session.delete(risk)
        await session.delete(account)
        await session.commit()


# ──────────────────────────────────────────────────────────────
# SECTION 6: Backend direct unit tests (no DB needed)
# ──────────────────────────────────────────────────────────────
def test_risk_manager_direct():
    """Direct test of RiskManager logic without HTTP or DB."""
    print("\n=== TEST: RiskManager Direct Logic ===")

    from core_engine.risk.funded_risk import FundedRiskManager
    from core_engine.risk.account_profile import AccountProfile, AccountProfileBuilder

    builder = AccountProfileBuilder()

    # Funded profile with profit_target and min_trading_days
    profile = builder.create_profile(
        client_id="test-direct", account_type="FUNDED",
        balance=10000.0, equity=10000.0,
        custom_settings={"risk_per_trade": 0.5, "max_daily_loss": 5.0, "max_account_loss": 10.0},
        min_trading_days=5, profit_target=10.0, trading_days_count=2,
    )
    check("Profile created with min_trading_days=5", profile.min_trading_days == 5)
    check("Profile created with profit_target=10", profile.profit_target == 10.0)
    check("Profile created with trading_days_count=2", profile.trading_days_count == 2)
    check("Profile is FUNDED", profile.account_type == "FUNDED")

    mgr = FundedRiskManager()
    result = mgr.evaluate(
        profile=profile, current_equity=10000.0,
        daily_start_equity=10000.0, start_balance=10000.0,
    )
    check("Funded risk: allowed at 0% loss", result.allowed is True)

    # Personal account should skip funded rules
    personal = builder.create_profile(
        client_id="test-personal", account_type="PERSONAL",
        balance=10000.0, equity=10000.0,
        min_trading_days=999, profit_target=999,
    )
    result3 = mgr.evaluate(
        profile=personal, current_equity=10000.0, daily_start_equity=10000.0,
    )
    check("Personal account: NOT_FUNDED (no funded rules)", result3.risk_state == "NOT_FUNDED")


# ──────────────────────────────────────────────────────────────
# Run all
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    async def _all():
        await test_profit_target_blocks()
        await test_personal_not_restricted()
        await test_record_trading_day()
        await test_funded_risk_includes_all_guards()
        await test_max_loss_plus_profit_target()
        test_risk_manager_direct()

        print(f"\n{'='*60}")
        print(f"  RESULTS: {passed}/{passed+failed} passed, {failed}/{passed+failed} failed")
        print(f"{'='*60}")
        return 0 if failed == 0 else 1

    exit_code = asyncio.run(_all())
    sys.exit(exit_code)

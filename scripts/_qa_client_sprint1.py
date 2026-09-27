"""QA for Client Dashboard Sprint 1: Home, Profile, License, Subscription.

Scenarios covered:
  - active   user: active license + subscription + accounts + trades (full state)
  - expired  user: expired license + inactive subscription (past end date)
  - suspended user: license status "suspended", account engine SUSPENDED
  - empty    user: fresh account, no license/subscription/trades (empty states)
  - profile PATCH validation (valid, bad language, empty body, email ignored)
  - subscription cancel / renew flows + cancel with no subscription -> 404
  - unauthenticated -> 401

Idempotent: reseeds the four test users and plan definitions every run.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:cimoro2008@localhost:5432/ict_funded_ea_qa"
os.environ["ENCRYPTION_KEY"] = "XLX1vxl3BclZbOETIL-StfxdVDrWeRj5VBCG-eEQpr0="

PASSWORD = "Passw0rd!123"

RESULTS: list[tuple[bool, str]] = []


def check(cond: bool, label: str):
    RESULTS.append((bool(cond), label))
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}")


async def _seed(s):
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import delete, select
    from database.base import Base
    from database.models import (
        AccountScan, AuditLog, License, LoginSession, PaperTrade, PlanDefinition,
        RiskProfile, Role, Subscription, TradingAccount, User,
    )
    from security.access_control import seed_roles_and_permissions
    from security.audit import log_event
    from security.password import hash_password

    await s.run_sync(lambda c: Base.metadata.create_all(c.bind))
    await seed_roles_and_permissions(s)
    role = (await s.execute(select(Role).where(Role.name == "client"))).scalar_one_or_none()
    now = datetime.now(timezone.utc)

    # --- plan definitions (idempotent upsert) ---------------------------------
    plans = [
        ("starter", "Starter", 29.0, 1, 0),
        ("professional", "Professional", 59.0, 3, 1),
        ("elite", "Elite", 99.0, 5, 2),
    ]
    for pid, name, price, max_acc, order in plans:
        if not await s.get(PlanDefinition, pid):
            s.add(PlanDefinition(id=pid, name=name, price_monthly=price,
                                 price_yearly=price * 10, max_accounts=max_acc,
                                 max_daily_loss=500.0, max_risk_per_trade=0.5,
                                 sort_order=order))
    await s.flush()

    async def reset(email: str):
        u = (await s.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if not u:
            return None
        accts = (await s.execute(
            select(TradingAccount).where(TradingAccount.user_id == u.id))).scalars().all()
        for a in accts:
            await s.execute(delete(RiskProfile).where(RiskProfile.account_id == a.id))
            await s.execute(delete(AccountScan).where(AccountScan.account_id == a.id))
            await s.execute(delete(PaperTrade).where(PaperTrade.account_id == a.id))
        await s.execute(delete(TradingAccount).where(TradingAccount.user_id == u.id))
        await s.execute(delete(License).where(License.user_id == u.id))
        await s.execute(delete(Subscription).where(Subscription.user_id == u.id))
        await s.execute(delete(LoginSession).where(LoginSession.user_id == u.id))
        await s.execute(delete(AuditLog).where(AuditLog.user_id == u.id))
        await s.execute(delete(User).where(User.id == u.id))
        await s.flush()

    async def new_user(email: str, first: str) -> User:
        u = User(email=email, password_hash=hash_password(PASSWORD),
                 first_name=first, last_name="Tester",
                 role_id=role.id if role else None,
                 account_status="active", email_verified=True, language="EN",
                 timezone="Africa/Casablanca", country="MA")
        s.add(u)
        await s.flush()
        return u

    # --- active user ----------------------------------------------------------
    await reset("sprint-active@testmail.com")
    u = await new_user("sprint-active@testmail.com", "Active")
    lic = License(user_id=u.id, license_key=f"QA-ACTIVE-{u.id[:6]}", plan="professional",
                  status="active", max_accounts=3,
                  expires_at=now + timedelta(days=28))
    s.add(lic)
    await s.flush()
    s.add(Subscription(user_id=u.id, plan="professional", billing_cycle="monthly",
                       price=59.0, start_date=now - timedelta(days=2),
                       end_date=now + timedelta(days=28), active=True))
    acc = TradingAccount(user_id=u.id, account_type="FUNDED", platform="MT5",
                         account_fingerprint=f"QA-ACTIVE-FP-{u.id[:6]}", active=True,
                         verified=True, engine_status="ACTIVE",
                         balance_snapshot=10000.0, equity_snapshot=10135.7,
                         login="9001", name="Active MT5", license_id=lic.id)
    s.add(acc)
    await s.flush()
    for sym, pnl, closed in (("XAUUSD", 120.5, True), ("EURUSD", -40.0, True),
                             ("GBPUSD", 55.2, True), ("XAUUSD", 0.0, False)):
        s.add(PaperTrade(user_id=u.id, account_id=acc.id, symbol=sym, direction="BUY",
                         status="CLOSED" if closed else "PLANNED",
                         entry_price=1.0, stop_loss=0.9, take_profit=1.1,
                         realized_pnl=pnl if closed else None,
                         realized_r=2.0 if closed else None,
                         created_at=now - timedelta(days=2),
                         closed_at=now if closed else None))
    await log_event(s, "license.activated", "License activated", user_id=u.id)
    await log_event(s, "license.bind", "License bound to account",
                    user_id=u.id, account_id=acc.id)
    await log_event(s, "payment.success", "Payment received - Professional monthly",
                    user_id=u.id, severity="SUCCESS",
                    payload={"amount": 59.0, "currency": "USD", "method": "card"})

    # --- expired user ---------------------------------------------------------
    await reset("sprint-expired@testmail.com")
    u = await new_user("sprint-expired@testmail.com", "Expired")
    s.add(License(user_id=u.id, license_key=f"QA-EXPIRE-{u.id[:6]}", plan="standard",
                  status="expired", max_accounts=1,
                  expires_at=now - timedelta(days=5)))
    s.add(Subscription(user_id=u.id, plan="standard", billing_cycle="monthly",
                       price=29.0, start_date=now - timedelta(days=35),
                       end_date=now - timedelta(days=5), active=False))

    # --- suspended user -------------------------------------------------------
    await reset("sprint-suspended@testmail.com")
    u = await new_user("sprint-suspended@testmail.com", "Suspended")
    lic = License(user_id=u.id, license_key=f"QA-SUSPND-{u.id[:6]}", plan="standard",
                  status="suspended", max_accounts=1,
                  expires_at=now + timedelta(days=10))
    s.add(lic)
    await s.flush()
    s.add(TradingAccount(user_id=u.id, account_type="CHALLENGE", platform="MT5",
                         account_fingerprint=f"QA-SUSP-FP-{u.id[:6]}", active=True,
                         verified=True, engine_status="SUSPENDED",
                         balance_snapshot=5000.0, equity_snapshot=5000.0,
                         login="9002", name="Suspended MT5", license_id=lic.id))

    # --- empty user -----------------------------------------------------------
    await reset("sprint-empty@testmail.com")
    await new_user("sprint-empty@testmail.com", "Empty")

    await s.commit()


def _run_seed():
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    async def go():
        eng = create_async_engine(os.environ["DATABASE_URL"])
        factory = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
        try:
            async with factory() as s:
                await _seed(s)
        finally:
            await eng.dispose()
    asyncio.run(go())


def _login(c, email):
    r = c.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def main():
    _run_seed()

    from fastapi.testclient import TestClient
    from api.main import app

    with TestClient(app) as c:
        H_active = _login(c, "sprint-active@testmail.com")
        H_expired = _login(c, "sprint-expired@testmail.com")
        H_suspended = _login(c, "sprint-suspended@testmail.com")
        H_empty = _login(c, "sprint-empty@testmail.com")

        # ---- dashboard: active ------------------------------------------------
        print("\n[1] Dashboard - active user")
        r = c.get("/api/client/dashboard", headers=H_active)
        check(r.status_code == 200, f"dashboard 200 (got {r.status_code})")
        d = r.json()
        check(d["license"]["status"] == "active", f"license.status=active (got {d['license']['status']})")
        check(d["license"]["used_accounts"] == 1, f"used_accounts=1 (got {d['license']['used_accounts']})")
        check(d["license"]["days_remaining"] >= 27, f"days_remaining>=27 (got {d['license']['days_remaining']})")
        check(d["subscription"]["active"] is True, "subscription.active=True")
        check(d["trading_status"]["running"] is True, "trading_status.running=True")
        check(d["trading_status"]["mt5_connected"] is True, "trading_status.mt5_connected=True")
        check(d["totals"]["total_trades"] == 3, f"totals.total_trades=3 (got {d['totals']['total_trades']})")
        check(d["today"]["closed_trades"] >= 1, f"today.closed_trades>=1 (got {d['today']['closed_trades']})")
        check(d["equity_curve"] and len(d["equity_curve"]) == 3,
              f"equity_curve length 3 (got {len(d['equity_curve'])})")

        # ---- dashboard: expired ------------------------------------------------
        print("\n[2] Dashboard - expired user")
        r = c.get("/api/client/dashboard", headers=H_expired)
        check(r.status_code == 200, f"dashboard 200 (got {r.status_code})")
        d = r.json()
        check(d["subscription"]["active"] is False, "subscription.active=False")
        check(d["subscription"]["days_remaining"] == 0, f"subscription.days_remaining=0 (got {d['subscription']['days_remaining']})")

        # ---- dashboard: suspended ----------------------------------------------
        print("\n[3] Dashboard - suspended user")
        r = c.get("/api/client/dashboard", headers=H_suspended)
        check(r.status_code == 200, f"dashboard 200 (got {r.status_code})")
        d = r.json()
        check(d["license"]["status"] == "suspended", f"license.status=suspended (got {d['license']['status']})")
        check(d["trading_status"]["running"] is False, "trading_status.running=False (suspended)")

        # ---- dashboard: empty user ---------------------------------------------
        print("\n[4] Dashboard - empty user (empty state)")
        r = c.get("/api/client/dashboard", headers=H_empty)
        check(r.status_code == 200, f"dashboard 200 (got {r.status_code})")
        d = r.json()
        check(d["license"] is None, "license=None")
        check(d["subscription"] is None, "subscription=None")
        check(d["equity_curve"] == [], "equity_curve=[]")
        check(d["recent_signals"] == [] and d["recent_trades"] == [], "recent signals/trades empty")
        check(d["totals"]["total_trades"] == 0 and d["trading_status"]["running"] is False,
              "totals zero + trading not running")

        # ---- profile ------------------------------------------------------------
        print("\n[5] Profile")
        r = c.get("/api/client/profile", headers=H_active)
        check(r.status_code == 200, f"profile 200 (got {r.status_code})")
        email = r.json()["email"]
        check(email == "sprint-active@testmail.com", "profile email matches")
        r = c.patch("/api/client/profile", headers=H_active,
                    json={"first_name": "Active2", "country": "FR", "language": "fr",
                          "timezone": "Europe/Paris", "avatar": "https://x/a.png"})
        check(r.status_code == 200, f"patch valid 200 (got {r.status_code})")
        p = r.json()["profile"]
        check(p["language"] == "FR", f"language normalized to FR (got {p['language']})")
        check(p["first_name"] == "Active2" and p["timezone"] == "Europe/Paris", "first_name/timezone saved")
        r = c.patch("/api/client/profile", headers=H_active, json={"language": "XX"})
        check(r.status_code == 400, f"invalid language -> 400 (got {r.status_code})")
        r = c.patch("/api/client/profile", headers=H_active, json={})
        check(r.status_code == 400, f"empty body -> 400 (got {r.status_code})")
        r = c.patch("/api/client/profile", headers=H_active, json={"email": "hacked@x.com"})
        check(r.status_code == 400, f"no valid fields (email ignored) -> 400 (got {r.status_code})")
        r = c.get("/api/client/profile", headers=H_active)
        check(r.json()["email"] == email, "email unchanged after patch attempt")

        # ---- license ------------------------------------------------------------
        print("\n[6] License")
        r = c.get("/api/client/license", headers=H_active)
        check(r.status_code == 200, f"license 200 (got {r.status_code})")
        j = r.json()
        check(len(j["items"]) == 1, f"one license item (got {len(j['items'])})")
        check(j["items"][0]["license_key"].startswith("QA-ACTIVE-"), "license key format")
        check(j["items"][0]["used_accounts"] == 1, f"license used_accounts=1 (got {j['items'][0]['used_accounts']})")
        check(j["items"][0]["days_remaining"] >= 27, "license days_remaining>=27")
        types = [h["event_type"] for h in j["activation_history"]]
        check("license.activated" in types, f"activation_history has license.activated (got {types})")
        r = c.get("/api/client/license", headers=H_suspended)
        check(r.json()["items"][0]["status"] == "suspended", "suspended license status")
        r = c.get("/api/client/license", headers=H_empty)
        check(r.json()["total"] == 0 and r.json()["activation_history"] == [],
              "empty user license -> 0 items, no history")

        # ---- subscription ---------------------------------------------------------
        print("\n[7] Subscription")
        r = c.get("/api/client/subscription", headers=H_active)
        check(r.status_code == 200, f"subscription 200 (got {r.status_code})")
        j = r.json()
        check(j["subscription"]["plan_name"] == "Professional", f"plan_name=Professional (got {j['subscription']['plan_name']})")
        check(j["subscription"]["active"] is True, "subscription active")
        check(len(j["available_plans"]) == 3, f"available_plans=3 (got {len(j['available_plans'])})")
        check(len(j["invoices"]) == 1 and j["invoices"][0]["status"] == "paid",
              f"invoice paid (got {[i['status'] for i in j['invoices']]})")
        check(j["payment_method"] == "card", f"payment_method=card (got {j['payment_method']})")
        r = c.get("/api/client/subscription", headers=H_expired)
        check(r.json()["subscription"]["active"] is False, "expired subscription inactive")
        r = c.get("/api/client/subscription", headers=H_empty)
        j = r.json()
        check(j["subscription"] is None and j["invoices"] == [], "empty user -> no subscription/invoices")

        # ---- cancel / renew -------------------------------------------------------
        print("\n[8] Subscription cancel / renew")
        r = c.post("/api/client/subscription/cancel", headers=H_active)
        check(r.status_code == 200, f"cancel 200 (got {r.status_code})")
        r = c.get("/api/client/subscription", headers=H_active)
        check(r.json()["subscription"]["active"] is False, "subscription inactive after cancel")
        r = c.post("/api/client/subscription/renew", headers=H_active)
        check(r.status_code == 200, f"renew 200 (got {r.status_code})")
        renew_date = r.json().get("renew_date")
        from datetime import datetime as _dt, timezone as _tz
        check(renew_date and _dt.fromisoformat(renew_date) > _dt.now(_tz.utc), "renew_date in future")
        r = c.get("/api/client/subscription", headers=H_active)
        check(r.json()["subscription"]["active"] is True, "subscription active after renew")
        r = c.post("/api/client/subscription/cancel", headers=H_empty)
        check(r.status_code == 404, f"cancel with no subscription -> 404 (got {r.status_code})")

        # ---- auth guard -----------------------------------------------------------
        print("\n[9] Auth guard")
        r = c.get("/api/client/dashboard")
        check(r.status_code == 401, f"unauthenticated -> 401 (got {r.status_code})")

    passed = sum(1 for ok, _ in RESULTS if ok)
    total = len(RESULTS)
    print(f"\n=== Sprint 1 QA: {passed}/{total} PASS ===")
    if passed != total:
        print("Failed checks:")
        for ok, label in RESULTS:
            if not ok:
                print(f"  - {label}")
        sys.exit(1)


if __name__ == "__main__":
    main()

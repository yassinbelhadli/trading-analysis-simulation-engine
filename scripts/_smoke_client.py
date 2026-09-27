"""Quick smoke test for new client Sprint-1 endpoints."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:cimoro2008@localhost:5432/ict_funded_ea_qa"
os.environ["ENCRYPTION_KEY"] = "XLX1vxl3BclZbOETIL-StfxdVDrWeRj5VBCG-eEQpr0="


def _seed_user(email, with_sub, with_license, with_trades):
    async def _do_all(s):
        from sqlalchemy import select
        from database.base import Base
        from database.models import User, Role, Subscription, License, PaperTrade, TradingAccount
        from security.access_control import seed_roles_and_permissions
        from security.password import hash_password
        from datetime import datetime, timedelta, timezone
        await s.run_sync(lambda c: Base.metadata.create_all(c.bind))
        await seed_roles_and_permissions(s)
        role = (await s.execute(select(Role).where(Role.name == "client"))).scalar_one_or_none()
        u = (await s.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if not u:
            u = User(email=email, password_hash=hash_password("Passw0rd!123"),
                     first_name="Smoke", last_name="User", role_id=role.id if role else None,
                     account_status="active", email_verified=True, language="EN")
            s.add(u)
            await s.flush()
        sub = (await s.execute(select(Subscription).where(Subscription.user_id == u.id))).scalar_one_or_none()
        if with_sub and not sub:
            s.add(Subscription(user_id=u.id, plan="professional", active=True,
                               billing_cycle="monthly", price=59.0,
                               start_date=datetime.now(timezone.utc),
                               end_date=datetime.now(timezone.utc) + timedelta(days=28)))
        if with_license and not (await s.execute(select(License).where(License.user_id == u.id))).scalars().all():
            lic = License(user_id=u.id, license_key=f"SMOKE-{u.id[:6]}", plan="professional",
                          status="active", max_accounts=3,
                          expires_at=datetime.now(timezone.utc) + timedelta(days=28))
            s.add(lic)
            await s.flush()
        else:
            lic = (await s.execute(select(License).where(License.user_id == u.id))).scalars().first()
        acc = (await s.execute(select(TradingAccount).where(TradingAccount.user_id == u.id))).scalars().first()
        if not acc:
            acc = TradingAccount(user_id=u.id, account_type="PERSONAL", platform="MT5",
                                 account_fingerprint=f"SMOKE-{u.id[:6]}", active=True,
                                 verified=True, engine_status="ACTIVE", balance_snapshot=10000.0,
                                 equity_snapshot=10135.7, login="12345678", name="Smoke MT5",
                                 license_id=lic.id if lic else None)
            s.add(acc)
            await s.flush()
        if with_trades:
            existing = (await s.execute(select(PaperTrade).where(PaperTrade.user_id == u.id))).scalars().all()
            if not existing:
                for sym, pnl, st in (("XAUUSD", 120.5, "CLOSED"), ("EURUSD", -40.0, "CLOSED"),
                                     ("GBPUSD", 55.2, "CLOSED"), ("XAUUSD", 0.0, "PLANNED")):
                    s.add(PaperTrade(user_id=u.id, account_id=acc.id, symbol=sym, direction="BUY", status=st,
                                     entry_price=1.0, stop_loss=0.9, take_profit=1.1,
                                     realized_pnl=pnl if st == "CLOSED" else None,
                                     created_at=datetime.now(timezone.utc),
                                     closed_at=datetime.now(timezone.utc) if st == "CLOSED" else None))
        await s.commit()
        return u.id
    return _run(_do_all)


def _run(fn):
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    async def go():
        eng = create_async_engine(os.environ["DATABASE_URL"])
        factory = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
        try:
            async with factory() as s:
                return await fn(s)
        finally:
            await eng.dispose()
    return asyncio.run(go())


def main():
    email = "smoke@testmail.com"
    _seed_user(email, True, True, True)

    from fastapi.testclient import TestClient
    from api.main import app

    with TestClient(app) as c:
        r = c.post("/auth/login", json={"email": email, "password": "Passw0rd!123"})
        assert r.status_code == 200, r.text
        H = {"Authorization": "Bearer " + r.json()["access_token"]}

        r = c.get("/api/client/dashboard", headers=H)
        print("dashboard:", r.status_code)
        if r.status_code != 200:
            print(r.text)
        else:
            d = r.json()
            print("  license:", d["license"])
            print("  subscription:", d["subscription"])
            print("  trading_status:", d["trading_status"])
            print("  today:", d["today"])
            print("  totals:", d["totals"])
            print("  recent_signals:", len(d["recent_signals"]), "recent_trades:", len(d["recent_trades"]))

        r = c.get("/api/client/profile", headers=H)
        print("profile:", r.status_code, r.json() if r.status_code == 200 else r.text)

        r = c.patch("/api/client/profile", headers=H,
                    json={"first_name": "Smoke2", "country": "MA", "language": "ar", "avatar": "https://x/a.png"})
        print("patch profile:", r.status_code, r.json() if r.status_code == 200 else r.text)

        r = c.get("/api/client/license", headers=H)
        print("license:", r.status_code)
        if r.status_code == 200:
            j = r.json()
            print("  items:", [(i["plan"], i["status"], i["max_accounts"], i["used_accounts"]) for i in j["items"]])
            print("  history:", j["activation_history"])

        r = c.get("/api/client/subscription", headers=H)
        print("subscription:", r.status_code)
        if r.status_code == 200:
            j = r.json()
            print("  sub:", j["subscription"])
            print("  plans:", [(p["id"], p["name"], p["price_monthly"]) for p in j["available_plans"]])

        r = c.post("/api/client/subscription/renew", headers=H)
        print("renew:", r.status_code, r.json() if r.status_code == 200 else r.text)

        r = c.post("/api/client/subscription/cancel", headers=H)
        print("cancel:", r.status_code, r.json() if r.status_code == 200 else r.text)

        r = c.get("/api/client/subscription", headers=H)
        print("sub after cancel:", r.json()["subscription"]["active"] if r.status_code == 200 else r.text)


if __name__ == "__main__":
    main()

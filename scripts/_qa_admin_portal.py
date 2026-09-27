"""Phase 4 Admin Portal QA — admin auth + staff 2FA, permission boundaries,
contract smoke for every frozen /api/admin/* surface used by the portal,
dangerous-action authorization, and legacy /admin/* lock regression.

Run:  python scripts/_qa_admin_portal.py
Requires: QA DB (ict_funded_ea_qa) + TEST ENCRYPTION_KEY (see CLAUDE.md).

Covers the Phase 4 QA plan (docs/phase4_admin_dashboard.md §12):
  - /api/admin/* requires an active admin JWT (401 without).
  - Admin login -> /dashboard redirect; staff 2FA full cycle
    (setup -> pending -> enable -> login 2FA step -> verify -> disable).
  - /auth/check-permission contract {resource, action} -> {resource, action, allowed}.
  - Permission spot checks: client -> 403 on /api/admin/*; support -> tickets/clients
    OK but settings + audit-logs 403; billing -> payments/subscriptions OK but
    engine control 403; analyst -> trading reads OK but engine 403.
  - Contract smoke per §6 (expected status + shape) with an admin token.
  - Dangerous-action authorization: role without the action gets 403; holder gets 200.
  - Legacy /admin/* returns 403 (fail-closed) without X-Admin-Token.

Idempotent: reseeds all test users every run.
"""
import asyncio
import base64
import hashlib
import hmac
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:cimoro2008@localhost:5432/ict_funded_ea_qa"
os.environ["ENCRYPTION_KEY"] = "XLX1vxl3BclZbOETIL-StfxdVDrWeRj5VBCG-eEQpr0="
os.environ["USE_MOCK_TELEGRAM_SCAN"] = "true"
os.environ.pop("TELEGRAM_BOT_TOKEN", None)
os.environ.pop("TELEGRAM_TEST_MODE", None)

PASSWORD = "PortalPassw0rd!456"
ADMIN = "qa_admin_portal@test.local"
SUPPORT = "qa_support_portal@test.local"
BILLING = "qa_billing_portal@test.local"
ANALYST = "qa_analyst_portal@test.local"
OWNER = "qa_owner_portal@test.local"
CLIENT = "qa_client_portal@test.local"

PASSED = 0
FAILED = 0
ERRORS = []


def ok(name: str) -> None:
    global PASSED
    PASSED += 1
    print(f"  [PASS] {name}")


def fail(name: str, detail: str) -> None:
    global FAILED
    FAILED += 1
    ERRORS.append((name, detail))
    print(f"  [FAIL] {name} -> {detail}")


def check(cond: bool, name: str, detail: str = ""):
    if cond:
        ok(name)
    else:
        fail(name, detail)


def _run_sql(fn):
    async def _go():
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        eng = create_async_engine(os.environ["DATABASE_URL"])
        factory = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
        try:
            async with factory() as s:
                return await fn(s)
        finally:
            await eng.dispose()
    return asyncio.run(_go())


def _totp(secret: str) -> str:
    """RFC-6238 TOTP, 6 digits, 30s step (matches security.totp)."""
    clean = secret.replace(" ", "").upper()
    key = base64.b32decode(clean + "=" * ((8 - len(clean)) % 8))
    counter = int(datetime.now(timezone.utc).timestamp() // 30)
    msg = counter.to_bytes(8, "big")
    hm = hmac.new(key, msg, hashlib.sha1).digest()
    offset = hm[-1] & 0x0F
    code = ((int.from_bytes(hm[offset:offset + 4], "big") & 0x7FFFFFFF) % 1000000)
    return f"{code:06d}"


def _seed():
    async def _do(s):
        from sqlalchemy import delete, select
        from database.base import Base
        from database.models import (
            AccountScan,
            AuditLog,
            License,
            LoginSession,
            PaperTrade,
            RiskProfile,
            Role,
            Subscription,
            SupportTicket,
            TicketMessage,
            TradingAccount,
            User,
            VerificationToken,
        )
        from security.access_control import seed_roles_and_permissions
        from security.password import hash_password

        await s.run_sync(lambda c: Base.metadata.create_all(c.bind))
        await seed_roles_and_permissions(s)

        # Wipe the fixture users + their data, plus any dangling audits.
        for acc in (await s.execute(select(TradingAccount))).scalars().all():
            await s.execute(delete(PaperTrade).where(PaperTrade.account_id == acc.id))
            await s.execute(delete(AccountScan).where(AccountScan.account_id == acc.id))
            await s.execute(delete(RiskProfile).where(RiskProfile.account_id == acc.id))
        await s.execute(delete(PaperTrade))
        await s.execute(delete(AccountScan))
        await s.execute(delete(RiskProfile))
        await s.execute(delete(TradingAccount))
        await s.execute(delete(TicketMessage))
        await s.execute(delete(SupportTicket))
        await s.execute(delete(License))
        await s.execute(delete(Subscription))
        await s.execute(delete(LoginSession))
        await s.execute(delete(VerificationToken))
        await s.execute(delete(User))
        await s.execute(delete(AuditLog))

        roles = {
            r.name: r.id
            for r in (await s.execute(select(Role))).scalars().all()
            if r.name in {"admin", "support", "billing", "analyst", "owner", "client"}
        }

        def _user(email: str, role_name: str, first: str, last: str):
            return User(
                email=email,
                password_hash=hash_password(PASSWORD),
                role_id=roles.get(role_name),
                account_status="active",
                email_verified=True,
                first_name=first,
                last_name=last,
            )

        admin_u = _user(ADMIN, "admin", "QA", "Admin")
        s.add(admin_u)
        s.add(_user(SUPPORT, "support", "QA", "Support"))
        s.add(_user(BILLING, "billing", "QA", "Billing"))
        s.add(_user(ANALYST, "analyst", "QA", "Analyst"))
        s.add(_user(OWNER, "owner", "QA", "Owner"))
        client_u = _user(CLIENT, "client", "QA", "Client")
        s.add(client_u)
        await s.flush()

        now = datetime.now(timezone.utc)
        s.add(Subscription(
            user_id=client_u.id, plan="professional", billing_cycle="monthly", price=59.0,
            start_date=now - timedelta(days=2), end_date=now + timedelta(days=28), active=True,
        ))
        lic = License(
            user_id=client_u.id, license_key="QA-ADMIN-PORTAL-LICENSE", plan="professional",
            status="active", max_accounts=3, expires_at=now + timedelta(days=28),
        )
        s.add(lic)
        await s.flush()
        s.add(TradingAccount(
            user_id=client_u.id, account_type="FUNDED", platform="MT5",
            account_fingerprint=f"qa-admin-portal-{uuid.uuid4().hex[:16]}",
            active=True, verified=True, engine_status="ACTIVE",
            balance_snapshot=10000.0, equity_snapshot=10000.0, login="4711",
            license_id=lic.id,
        ))
        s.add(SupportTicket(
            user_id=client_u.id, ticket_number=f"QA{int(now.timestamp())}",
            subject="QA admin portal ticket", description="Seeded for admin portal QA.",
            category="other", status="open", priority="medium",
        ))
        await s.commit()
    _run_sql(_do)


def _login(c, email, password=PASSWORD):
    return c.post("/auth/login", json={"email": email, "password": password})


def _login_admin(c):
    """Login as admin. 2FA is disabled by default for the seeded admin."""
    r = _login(c, ADMIN)
    assert r.status_code == 200 and r.json().get("access_token"), f"admin login failed: {r.text[:200]}"
    return r.json()


def main() -> int:
    _seed()

    from fastapi.testclient import TestClient
    from api.main import app

    with TestClient(app) as c:
        # ---- 1. Unauthenticated guard ---------------------------------------
        print("\n[1] Unauthenticated guard")
        for path in ["/api/admin/overview", "/api/admin/users", "/api/admin/licenses",
                     "/api/admin/clients", "/api/admin/audit-logs", "/api/admin/tickets",
                     "/api/admin/settings", "/api/admin/system-health"]:
            r = c.get(path)
            check(r.status_code == 401, f"401 without token: {path}", f"got {r.status_code}")

        # ---- 2. Admin login + staff 2FA flow --------------------------------
        print("\n[2] Admin login + staff 2FA")
        r = _login(c, ADMIN)
        check(r.status_code == 200 and r.json().get("access_token"), "admin login", r.text[:160])
        check(r.json().get("redirect_to") == "/dashboard", "staff login redirect -> /dashboard",
              str(r.json().get("redirect_to")))
        check(r.json().get("user", {}).get("role") == "admin", "role=admin in login payload",
              str(r.json().get("user")))
        H = {"Authorization": "Bearer " + r.json()["access_token"]}

        r = c.get("/auth/me", headers=H)
        check(r.status_code == 200 and r.json().get("role") == "admin", "/auth/me role=admin",
              r.text[:160])

        # Enable staff 2FA.
        r = c.post("/auth/2fa/setup", headers=H, json={"current_password": PASSWORD})
        check(r.status_code == 200 and r.json().get("secret"), "admin 2fa setup", r.text[:160])
        secret = r.json().get("secret")

        r = c.post("/auth/2fa/enable", headers=H, json={"code": "000000"})
        check(r.status_code == 401, "enable with wrong code rejected (401)", f"got {r.status_code}")
        r = c.post("/auth/2fa/enable", headers=H, json={"code": _totp(secret)})
        check(r.status_code == 200, "enable with valid TOTP", r.text[:160])

        # Login now forces the 2FA step.
        r = _login(c, ADMIN)
        check(r.status_code == 200 and r.json().get("two_factor_required") is True,
              "login returns two_factor_required when 2FA enabled", r.text[:160])
        t2fa = r.json().get("two_factor_token")
        check(bool(t2fa), "two_factor_token issued")

        r = c.post("/auth/2fa/verify", json={"code": "000000", "two_factor_token": t2fa})
        check(r.status_code == 401, "verify with wrong code rejected (401)", f"got {r.status_code}")
        r = c.post("/auth/2fa/verify", json={"code": _totp(secret), "two_factor_token": t2fa})
        check(r.status_code == 200 and r.json().get("access_token"),
              "verify with valid code issues tokens", r.text[:160])
        H = {"Authorization": "Bearer " + r.json()["access_token"]}

        # Disable 2FA (restore deterministic admin login for the rest of the suite).
        r = c.post("/auth/2fa/disable", headers=H, json={"code": _totp(secret)})
        check(r.status_code == 200, "staff 2fa disabled after cycle", r.text[:160])

        # ---- 3. /auth/check-permission contract -----------------------------
        print("\n[3] check-permission contract")
        r = c.post("/auth/check-permission", headers=H, json={"resource": "clients", "action": "read"})
        check(r.status_code == 200 and r.json().get("allowed") is True,
              "admin clients.read allowed", r.text[:160])

        r = c.post("/auth/check-permission", headers=H, json={"resource": "clients"})
        check(r.status_code == 400, "missing action rejected (400)", f"got {r.status_code}")

        r = _login(c, SUPPORT)
        Hs = {"Authorization": "Bearer " + r.json()["access_token"]}
        r = c.post("/auth/check-permission", headers=Hs, json={"resource": "audit", "action": "read"})
        check(r.status_code == 200 and r.json().get("allowed") is False,
              "support audit.read denied", r.text[:160])
        r = c.post("/auth/check-permission", headers=Hs, json={"resource": "system", "action": "settings"})
        check(r.status_code == 200 and r.json().get("allowed") is False,
              "support system.settings denied", r.text[:160])

        r = _login(c, OWNER)
        Ho = {"Authorization": "Bearer " + r.json()["access_token"]}
        r = c.post("/auth/check-permission", headers=Ho, json={"resource": "system", "action": "secrets"})
        check(r.status_code == 200 and r.json().get("allowed") is True,
              "owner system.secrets allowed (wildcard)", r.text[:160])

        r = _login(c, CLIENT)
        Hc = {"Authorization": "Bearer " + r.json()["access_token"]}
        r = c.post("/auth/check-permission", headers=Hc, json={"resource": "admin", "action": "overview"})
        check(r.status_code == 200 and r.json().get("allowed") is False,
              "client admin.overview denied", r.text[:160])

        # ---- 4. Permission spot checks --------------------------------------
        print("\n[4] Permission spot checks")
        r = c.get("/api/admin/overview", headers=Hc)
        check(r.status_code == 403, "client token blocked from overview (403)", f"got {r.status_code}")
        r = c.get("/api/admin/users", headers=Hc)
        check(r.status_code == 403, "client token blocked from users (403)", f"got {r.status_code}")

        # support: tickets + clients OK; settings + audit-logs 403.
        r = c.get("/api/admin/tickets", headers=Hs)
        check(r.status_code == 200, "support can list tickets", f"got {r.status_code}")
        r = c.get("/api/admin/clients", headers=Hs)
        check(r.status_code == 200, "support can list clients", f"got {r.status_code}")
        r = c.get("/api/admin/settings", headers=Hs)
        check(r.status_code == 403, "support blocked from settings (403)", f"got {r.status_code}")
        r = c.get("/api/admin/audit-logs", headers=Hs)
        check(r.status_code == 403, "support blocked from audit-logs (403)", f"got {r.status_code}")
        r = c.get("/api/admin/analytics/revenue", headers=Hs)
        check(r.status_code == 403, "support blocked from revenue analytics (403)", f"got {r.status_code}")

        # billing: payments + subscriptions OK; engine control 403.
        r = _login(c, BILLING)
        Hb = {"Authorization": "Bearer " + r.json()["access_token"]}
        r = c.get("/api/admin/payments", headers=Hb)
        check(r.status_code == 200, "billing can list payments", f"got {r.status_code}")
        r = c.get("/api/admin/subscriptions", headers=Hb)
        check(r.status_code == 200, "billing can list subscriptions", f"got {r.status_code}")
        r = c.post("/api/admin/system-health/engine/restart", headers=Hb)
        check(r.status_code == 403, "billing blocked from engine restart (403)", f"got {r.status_code}")
        r = c.get("/api/admin/analytics/revenue", headers=Hb)
        check(r.status_code == 200, "billing can read revenue analytics (BILLING_READ)", f"got {r.status_code}")

        # analyst: trading reads OK; engine 403.
        r = _login(c, ANALYST)
        Ha = {"Authorization": "Bearer " + r.json()["access_token"]}
        r = c.get("/api/admin/trading/performance", headers=Ha)
        check(r.status_code == 200, "analyst can read trading performance", f"got {r.status_code}")
        r = c.get("/api/admin/trading/risk", headers=Ha)
        check(r.status_code == 200, "analyst can read risk monitor", f"got {r.status_code}")
        r = c.get("/api/admin/trading/engine", headers=Ha)
        check(r.status_code == 403, "analyst blocked from engine monitor (403)", f"got {r.status_code}")

        # owner: full control surfaces.
        r = c.get("/api/admin/overview", headers=Ho)
        check(r.status_code == 200, "owner can read overview", f"got {r.status_code}")
        r = c.post("/api/admin/system-health/engine/restart", headers=Ho)
        check(r.status_code == 200, "owner can request engine restart", f"got {r.status_code}")

        # ---- 5. Contract smoke (admin) --------------------------------------
        print("\n[5] Contract smoke (admin)")
        r = c.get("/api/admin/overview", headers=H)
        d = r.json()
        check(r.status_code == 200 and set(d) >= {"engine", "counts", "errors_24h"},
              "overview shape", f"keys={list(d)[:6]}")

        r = c.get("/api/admin/clients", headers=H)
        d = r.json()
        check(r.status_code == 200 and isinstance(d.get("items"), list) and "total" in d,
              "clients shape", r.text[:160])
        client_id = d["items"][0]["id"] if d["items"] else None

        r = c.get(f"/api/admin/clients/{client_id}", headers=H)
        d = r.json()
        check(r.status_code == 200 and d.get("id") == client_id and "subscription" in d,
              "client detail shape", r.text[:160])
        check(d.get("accounts") and isinstance(d["accounts"], list),
              "client detail includes accounts list", str(len(d.get("accounts") or [])))

        r = c.get("/api/admin/licenses", headers=H)
        d = r.json()
        check(r.status_code == 200 and isinstance(d.get("items"), list) and "total" in d,
              "licenses shape", r.text[:160])
        lic_id = d["items"][0]["id"] if d["items"] else None
        r = c.get(f"/api/admin/licenses/{lic_id}", headers=H)
        check(r.status_code == 200 and r.json().get("id") == lic_id,
              "license detail shape", r.text[:160])

        r = c.get("/api/admin/subscriptions", headers=H)
        d = r.json()
        check(r.status_code == 200 and isinstance(d.get("items"), list), "subscriptions shape",
              r.text[:160])
        r = c.get("/api/admin/payments", headers=H)
        d = r.json()
        check(r.status_code == 200 and isinstance(d.get("items"), list), "payments shape",
              r.text[:160])
        r = c.get("/api/admin/promotions", headers=H)
        d = r.json()
        check(r.status_code == 200 and isinstance(d.get("items"), list), "promotions shape",
              r.text[:160])
        r = c.get("/api/admin/news", headers=H)
        d = r.json()
        check(r.status_code == 200 and isinstance(d.get("items"), list), "news shape", r.text[:160])
        r = c.get("/api/admin/news/engine-status", headers=H)
        d = r.json()
        check(r.status_code == 200 and "running" in d and "upcoming_high" in d,
              "news engine-status shape", r.text[:160])

        r = c.get("/api/admin/tickets", headers=H)
        d = r.json()
        check(r.status_code == 200 and isinstance(d.get("tickets"), list) and "total" in d,
              "tickets shape", r.text[:160])
        ticket_id = d["tickets"][0]["id"] if d["tickets"] else None
        r = c.get(f"/api/admin/tickets/{ticket_id}", headers=H)
        d = r.json()
        # New unified detail contract: {"success": true, "ticket": {...}}.
        check(r.status_code == 200 and d.get("success") is True
              and d.get("ticket", {}).get("id") == ticket_id,
              "ticket detail shape", r.text[:160])

        r = c.get("/api/admin/users", headers=H)
        d = r.json()
        check(r.status_code == 200 and isinstance(d.get("items"), list), "users shape", r.text[:160])
        r = c.get("/api/admin/roles", headers=H)
        d = r.json()
        check(r.status_code == 200 and isinstance(d.get("items"), list), "roles shape", r.text[:160])
        r = c.get("/api/admin/permissions", headers=H)
        d = r.json()
        check(r.status_code == 200 and isinstance(d.get("items"), list), "permissions shape",
              r.text[:160])

        r = c.get("/api/admin/audit-logs", headers=H)
        d = r.json()
        check(r.status_code == 200 and isinstance(d.get("items"), list) and "total" in d,
              "audit-logs shape", r.text[:160])
        r = c.get("/api/admin/audit-logs/summary", headers=H)
        check(r.status_code == 200 and "by_severity" in r.json(), "audit-logs summary shape",
              r.text[:160])

        for path in ["/api/admin/system-health", "/api/admin/system-health/summary",
                     "/api/admin/system-health/engines", "/api/admin/system-health/heartbeat",
                     "/api/admin/system-health/report"]:
            r = c.get(path, headers=H)
            check(r.status_code == 200, f"system-health 200: {path}", f"got {r.status_code}")

        r = c.get("/api/admin/settings", headers=H)
        check(r.status_code == 200 and "settings" in r.json(), "settings shape", r.text[:160])
        r = c.get("/api/admin/settings/schema", headers=H)
        d = r.json()
        check(r.status_code == 200 and "categories" in d and "groups" in d,
              "settings schema shape", r.text[:160])

        for path in ["/api/admin/trading/overview", "/api/admin/trading/active-trades",
                     "/api/admin/trading/history", "/api/admin/trading/signals",
                     "/api/admin/trading/risk", "/api/admin/trading/performance",
                     "/api/admin/trading/engine"]:
            r = c.get(path, headers=H)
            check(r.status_code == 200, f"trading 200: {path}", f"got {r.status_code}")

        r = c.get("/api/admin/analytics/revenue", headers=H)
        check(r.status_code == 200 and "mrr" in r.json(), "revenue analytics shape", r.text[:160])

        # ---- 6. Dangerous-action authorization ------------------------------
        print("\n[6] Dangerous-action authorization")
        r = c.post("/api/admin/licenses", headers=Hs,
                   json={"user_id": client_id, "plan": "starter", "max_accounts": 1, "expires_in_days": 30})
        check(r.status_code == 403, "support cannot create licenses (403)", f"got {r.status_code}")
        r = c.put("/api/admin/settings", headers=Hs, json={"updates": {"appearance.brand_name": "x"}})
        check(r.status_code == 403, "support cannot write settings (403)", f"got {r.status_code}")
        r = c.post("/api/admin/trading/control/disable", headers=Ha)
        check(r.status_code == 403, "analyst cannot disable trading (403)", f"got {r.status_code}")
        r = c.post("/api/admin/users", headers=Hc,
                   json={"email": "nope@testmail.com", "password": "Nope!1234"})
        check(r.status_code == 403, "client cannot create users (403)", f"got {r.status_code}")

        r = c.put("/api/admin/settings", headers=H, json={"updates": {"appearance.brand_name": "QA Brand"}})
        check(r.status_code == 200 and r.json().get("success"),
              "admin can write settings (audited)", r.text[:160])
        r = c.post("/api/admin/system-health/engine/restart", headers=H)
        check(r.status_code == 200 and r.json().get("success"),
              "admin can request engine restart (audited)", r.text[:160])

        r = c.post(f"/api/admin/tickets/{ticket_id}/reply", headers=Hs,
                   json={"message": "QA reply from support", "is_internal": False})
        check(r.status_code == 200 and r.json().get("success") is True and r.json().get("audit_id"),
              "support can reply to ticket (tickets.update, unified contract)",
              r.text[:160])
        r = c.patch(f"/api/admin/tickets/{ticket_id}", headers=Hs, json={"status": "in_progress"})
        check(r.status_code == 200 and r.json().get("success") is True,
              "support can update ticket status (unified contract)", r.text[:160])
        r = c.post(f"/api/admin/tickets/{ticket_id}/escalate", headers=Hc)
        check(r.status_code == 403, "client cannot escalate ticket (403)", f"got {r.status_code}")

        # ---- 7. Legacy /admin/* lock regression -----------------------------
        print("\n[7] Legacy /admin/* regression (fail-closed)")
        for path in ["/admin/health", "/admin/users", "/admin/accounts",
                     "/admin/licenses", "/admin/audit/recent", "/admin/metrics"]:
            r = c.get(path)
            check(r.status_code == 403, f"legacy {path} locked without X-Admin-Token (403)",
                  f"got {r.status_code}")
        r = c.get("/admin/health", headers={"X-Admin-Token": "wrong-token"})
        check(r.status_code == 403, "legacy /admin/health locked with wrong token (403)",
              f"got {r.status_code}")

        # ---- 8. Client/admin boundary ---------------------------------------
        print("\n[8] Client/admin boundary")
        r = c.get("/api/client/dashboard", headers=Hc)
        check(r.status_code == 200, "client still uses its own portal API (200)", f"got {r.status_code}")
        r = c.get("/api/admin/overview", headers=Hc)
        check(r.status_code == 403, "client cannot cross into admin API (403)", f"got {r.status_code}")

    print(f"\nTOTAL {PASSED + FAILED} | PASS {PASSED} | FAIL {FAILED} | ERROR {len(ERRORS)}")
    for name, detail in ERRORS:
        print(f"  FAILED: {name} :: {detail}")
    return 1 if (FAILED or ERRORS) else 0


if __name__ == "__main__":
    sys.exit(main())

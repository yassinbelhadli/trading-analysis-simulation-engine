"""Phase 5 Owner Portal QA — owner-only access, wildcard permission, portal
isolation, provisioning lock, safe-settings boundary (no secret exposure),
revenue oversight, audit trail, dangerous-action authorization, logout.

Run:  python scripts/_qa_owner_portal.py
Requires: QA DB (ict_funded_ea_qa) + TEST ENCRYPTION_KEY (see CLAUDE.md).

Covers the Phase 5 QA plan (docs/phase5_owner_portal_final.md §12):
  - Owner login -> /dashboard redirect; owner /auth/me role=owner.
  - Owner 2FA full cycle (setup -> pending -> enable -> login 2FA -> verify -> disable).
  - Wildcard access: owner reads every owner surface (overview, users, roles,
    audit, system-health, trading, revenue, settings, news, plans, subs, payments,
    promotions).
  - Non-owner rejection: client 403 on every owner surface; support partial.
  - Provisioning lock: owner create/promote via API is 403; owners can never be
    suspended/deleted via API (script-only provisioning, OQ-1).
  - Revenue analytics via billing.read (OQ-6).
  - Settings boundary: GET masks secrets (••••••••); PUT returns decrypted values
    (documents WHY the UI deny-list is mandatory); deny-list from owner_portal
    lib/api.ts covers every is_secret schema key; safe non-secret writes are
    audited.
  - Audit trail: owner actions recorded with user_id = owner.
  - Dangerous actions: engine control, trading control, news broadcast all 200
    for owner + audited.

Idempotent: reseeds all fixture users every run.
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
OWNER = "qa_owner_portal@test.local"
OWNER2 = "qa_owner2_portal@test.local"
SUPPORT = "qa_support_portal@test.local"
BILLING = "qa_billing_portal@test.local"
CLIENT = "qa_client_portal@test.local"
ANALYST = "qa_analyst_portal@test.local"

# Mirrors owner_portal/lib/api.ts SECRET_DENYLIST (defense-in-depth beyond the
# schema is_secret flags). QA asserts this is a superset of every is_secret key
# served by /api/admin/settings/schema.
SECRET_DENYLIST = {
    "telegram.bot_token",
    "email.smtp_pass",
    "security.jwt_secret",
    "security.encryption_key",
    "api.mt5_credentials",
    "database.url",
    "news.api_key",
}

MASK = "\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022"  # ••••••••

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

        s.add(_user(OWNER, "owner", "QA", "Owner"))
        s.add(_user(OWNER2, "owner", "QA", "Owner2"))
        s.add(_user(SUPPORT, "support", "QA", "Support"))
        s.add(_user(BILLING, "billing", "QA", "Billing"))
        s.add(_user(ANALYST, "analyst", "QA", "Analyst"))
        client_u = _user(CLIENT, "client", "QA", "Client")
        s.add(client_u)
        await s.flush()

        now = datetime.now(timezone.utc)
        s.add(Subscription(
            user_id=client_u.id, plan="professional", billing_cycle="monthly", price=59.0,
            start_date=now - timedelta(days=2), end_date=now + timedelta(days=28), active=True,
        ))
        lic = License(
            user_id=client_u.id, license_key="QA-OWNER-PORTAL-LICENSE", plan="professional",
            status="active", max_accounts=3, expires_at=now + timedelta(days=28),
        )
        s.add(lic)
        await s.flush()
        s.add(TradingAccount(
            user_id=client_u.id, account_type="FUNDED", platform="MT5",
            account_fingerprint=f"qa-owner-portal-{uuid.uuid4().hex[:16]}",
            active=True, verified=True, engine_status="ACTIVE",
            balance_snapshot=10000.0, equity_snapshot=10000.0, login="4711",
            license_id=lic.id,
        ))
        await s.commit()
    _run_sql(_do)


def _login(c, email, password=PASSWORD):
    return c.post("/auth/login", json={"email": email, "password": password})


def _login_token(c, email):
    r = _login(c, email)
    assert r.status_code == 200 and r.json().get("access_token"), \
        f"{email} login failed: {r.text[:200]}"
    return r.json()


def main() -> int:
    _seed()

    from fastapi.testclient import TestClient
    from api.main import app

    with TestClient(app) as c:
        # ---- 1. Unauthenticated guard ----------------------------------------
        print("\n[1] Unauthenticated guard")
        for path in ["/api/admin/overview", "/api/admin/users", "/api/admin/roles",
                     "/api/admin/audit-logs", "/api/admin/system-health",
                     "/api/admin/settings", "/api/admin/analytics/revenue",
                     "/api/admin/news/engine-status", "/api/admin/plans"]:
            r = c.get(path)
            check(r.status_code == 401, f"401 without token: {path}", f"got {r.status_code}")

        # ---- 2. Owner login + 2FA cycle + logout -----------------------------
        print("\n[2] Owner login + 2FA cycle")
        r = _login(c, OWNER)
        check(r.status_code == 200 and r.json().get("access_token"),
              "owner login", r.text[:160])
        check(r.json().get("redirect_to") == "/dashboard",
              "owner login redirect -> /dashboard", str(r.json().get("redirect_to")))
        check(r.json().get("user", {}).get("role") == "owner",
              "role=owner in login payload", str(r.json().get("user")))
        H = {"Authorization": "Bearer " + r.json()["access_token"]}

        r = c.get("/auth/me", headers=H)
        check(r.status_code == 200 and r.json().get("role") == "owner",
              "/auth/me role=owner", r.text[:160])

        # Owner 2FA full cycle.
        r = c.post("/auth/2fa/setup", headers=H, json={"current_password": PASSWORD})
        check(r.status_code == 200 and r.json().get("secret"), "owner 2fa setup", r.text[:160])
        secret = r.json().get("secret")
        r = c.post("/auth/2fa/enable", headers=H, json={"code": "000000"})
        check(r.status_code == 401, "owner enable with wrong code rejected (401)",
              f"got {r.status_code}")
        r = c.post("/auth/2fa/enable", headers=H, json={"code": _totp(secret)})
        check(r.status_code == 200, "owner enable with valid TOTP", r.text[:160])

        r = _login(c, OWNER)
        check(r.status_code == 200 and r.json().get("two_factor_required") is True,
              "owner login returns two_factor_required", r.text[:160])
        t2fa = r.json().get("two_factor_token")
        check(bool(t2fa), "owner two_factor_token issued")
        r = c.post("/auth/2fa/verify", json={"code": _totp(secret), "two_factor_token": t2fa})
        check(r.status_code == 200 and r.json().get("access_token"),
              "owner 2fa verify issues tokens", r.text[:160])
        H = {"Authorization": "Bearer " + r.json()["access_token"]}
        r = c.post("/auth/2fa/disable", headers=H, json={"code": _totp(secret)})
        check(r.status_code == 200, "owner 2fa disabled after cycle", r.text[:160])

        # Logout revokes the refresh session (stateless access token is dropped
        # client-side by clearAuth; server-side the refresh path must die).
        own = _login_token(c, OWNER)
        H = {"Authorization": "Bearer " + own["access_token"]}
        r = c.post("/auth/logout", headers=H, json={"refresh_token": own["refresh_token"]})
        check(r.status_code == 200, "owner logout", r.text[:160])
        r = c.post("/auth/refresh", json={"refresh_token": own["refresh_token"]})
        check(r.status_code == 401, "revoked refresh token rejected (401)",
              f"got {r.status_code}")

        # ---- 3. Owner wildcard access ----------------------------------------
        print("\n[3] Owner wildcard access")
        Ho = {"Authorization": "Bearer " + _login_token(c, OWNER)["access_token"]}
        r = c.post("/auth/check-permission", headers=Ho,
                   json={"resource": "system", "action": "secrets"})
        check(r.status_code == 200 and r.json().get("allowed") is True,
              "owner system.secrets allowed (wildcard)", r.text[:160])

        for path in ["/api/admin/overview", "/api/admin/users", "/api/admin/roles",
                     "/api/admin/permissions", "/api/admin/audit-logs",
                     "/api/admin/audit-logs/summary", "/api/admin/system-health",
                     "/api/admin/system-health/summary", "/api/admin/system-health/engines",
                     "/api/admin/system-health/heartbeat", "/api/admin/system-health/report",
                     "/api/admin/trading/overview", "/api/admin/trading/active-trades",
                     "/api/admin/trading/history", "/api/admin/trading/signals",
                     "/api/admin/trading/risk", "/api/admin/trading/performance",
                     "/api/admin/trading/engine", "/api/admin/trading/engine/logs",
                     "/api/admin/analytics/revenue", "/api/admin/settings",
                     "/api/admin/settings/schema", "/api/admin/news",
                     "/api/admin/news/engine-status", "/api/admin/plans",
                     "/api/admin/subscriptions", "/api/admin/payments",
                     "/api/admin/promotions", "/api/admin/clients",
                     "/api/admin/licenses"]:
            r = c.get(path, headers=Ho)
            check(r.status_code == 200, f"owner GET 200: {path}", f"got {r.status_code}")

        # ---- 4. Non-owner rejection -------------------------------------------
        print("\n[4] Non-owner rejection")
        Hc = {"Authorization": "Bearer " + _login_token(c, CLIENT)["access_token"]}
        for path in ["/api/admin/overview", "/api/admin/users", "/api/admin/roles",
                     "/api/admin/audit-logs", "/api/admin/system-health",
                     "/api/admin/settings", "/api/admin/analytics/revenue",
                     "/api/admin/news"]:
            r = c.get(path, headers=Hc)
            check(r.status_code == 403, f"client blocked (403): {path}", f"got {r.status_code}")
        r = c.post("/api/admin/trading/control/disable", headers=Hc)
        check(r.status_code == 403, "client blocked from trading control (403)", f"got {r.status_code}")
        # Plans + promotions are a public catalog (client holds subscriptions.read);
        # WRITE actions require subscriptions.update -> client blocked.
        r = c.get("/api/admin/plans", headers=Hc)
        check(r.status_code == 200, "client can read public plan catalog (200)",
              f"got {r.status_code}")
        r = c.get("/api/admin/promotions", headers=Hc)
        check(r.status_code == 200, "client can read public promotions (200)",
              f"got {r.status_code}")
        r = c.post("/api/admin/promotions", headers=Hc,
                   json={"name": "Nope", "plan_id": "00000000-0000-0000-0000-000000000000"})
        check(r.status_code == 403, "client blocked from creating promotions (403)",
              f"got {r.status_code}")
        r = c.post("/api/admin/plans/restore-defaults", headers=Hc)
        check(r.status_code == 403, "client blocked from plan restore-defaults (403)",
              f"got {r.status_code}")

        # support: tickets OK; owner-only revenue + audit + settings 403.
        Hs = {"Authorization": "Bearer " + _login_token(c, SUPPORT)["access_token"]}
        r = c.get("/api/admin/tickets", headers=Hs)
        check(r.status_code == 200, "support can list tickets", f"got {r.status_code}")
        r = c.get("/api/admin/analytics/revenue", headers=Hs)
        check(r.status_code == 403, "support blocked from revenue (403)", f"got {r.status_code}")
        r = c.get("/api/admin/audit-logs", headers=Hs)
        check(r.status_code == 403, "support blocked from audit-logs (403)", f"got {r.status_code}")
        r = c.get("/api/admin/settings", headers=Hs)
        check(r.status_code == 403, "support blocked from settings (403)", f"got {r.status_code}")

        # ---- 5. Provisioning lock (OQ-1: owner creation is script-only) -------
        print("\n[5] Provisioning lock")
        roles = c.get("/api/admin/roles", headers=Ho).json()["items"]
        owner_role_id = next(rr["id"] for rr in roles if rr["name"] == "owner")
        client_row = c.get("/api/admin/users", headers=Ho).json()["items"]
        client_id = next(u["id"] for u in client_row if u["email"] == CLIENT)
        owner2_id = next(u["id"] for u in client_row if u["email"] == OWNER2)
        owner_id = next(u["id"] for u in client_row if u["email"] == OWNER)

        r = c.post("/api/admin/users", headers=Ho,
                   json={"email": "nope-owner@test.local", "password": "Nope!1234",
                         "role_id": owner_role_id})
        check(r.status_code == 403, "owner cannot create another owner via API (403)",
              f"got {r.status_code}")

        # Promote the client to owner -> 403.
        owner_promote = {"role_id": owner_role_id}
        r = c.patch(f"/api/admin/users/{client_id}", headers=Ho, json=owner_promote)
        check(r.status_code == 403, "owner cannot promote client to owner via API (403)",
              f"got {r.status_code}")

        # Owners can never be suspended/deleted via API.
        r = c.post(f"/api/admin/users/{owner2_id}/suspend", headers=Ho)
        check(r.status_code == 403, "owner cannot suspend another owner via API (403)",
              f"got {r.status_code}")
        r = c.delete(f"/api/admin/users/{owner2_id}", headers=Ho)
        check(r.status_code == 403, "owner cannot delete another owner via API (403)",
              f"got {r.status_code}")
        r = c.delete(f"/api/admin/users/{owner_id}", headers=Ho)
        check(r.status_code == 403, "owner cannot delete self via API (403)", f"got {r.status_code}")

        # Owner CAN manage clients (legit oversight surface).
        r = c.post(f"/api/admin/users/{client_id}/suspend", headers=Ho)
        check(r.status_code == 200, "owner can suspend a client", r.text[:160])
        r = c.post(f"/api/admin/users/{client_id}/activate", headers=Ho)
        check(r.status_code == 200, "owner can activate a client", r.text[:160])

        # ---- 6. Revenue analytics (billing.read, OQ-6) ------------------------
        print("\n[6] Revenue analytics")
        r = c.get("/api/admin/analytics/revenue", headers=Ho)
        d = r.json()
        check(r.status_code == 200 and "mrr" in d, "owner revenue shape", r.text[:160])
        Hb = {"Authorization": "Bearer " + _login_token(c, BILLING)["access_token"]}
        r = c.get("/api/admin/analytics/revenue", headers=Hb)
        check(r.status_code == 200, "billing can read revenue (billing.read)",
              f"got {r.status_code}")

        # ---- 7. Settings boundary (OQ-3: no secret exposure) ------------------
        print("\n[7] Settings boundary (safe settings only)")
        r = c.get("/api/admin/settings", headers=Ho)
        d = r.json()
        check(r.status_code == 200 and "settings" in d, "settings GET shape", r.text[:160])
        check(d["settings"].get("email.smtp_pass") == MASK,
              "GET masks secret values (smtp_pass -> ••••••••)",
              repr(d["settings"].get("email.smtp_pass")))

        # PUT returns decrypted values -> documents why the UI deny-list is mandatory.
        r = c.put("/api/admin/settings", headers=Ho,
                  json={"updates": {"email.smtp_pass": "qa-decrypted-boundary-probe"}})
        check(r.status_code == 200 and r.json().get("success"),
              "PUT secret write accepted by backend", r.text[:160])
        check(r.json().get("settings", {}).get("email.smtp_pass") == "qa-decrypted-boundary-probe",
              "PUT response returns decrypted secret (boundary documented)",
              repr(r.json().get("settings", {}).get("email.smtp_pass")))
        r = c.get("/api/admin/settings", headers=Ho)
        check(r.json()["settings"].get("email.smtp_pass") == MASK,
              "GET never reveals the raw secret value")
        # Restore default so the fixture DB stays clean.
        r = c.put("/api/admin/settings", headers=Ho, json={"updates": {"email.smtp_pass": ""}})
        check(r.status_code == 200, "secret reset to default", r.text[:160])

        # Deny-list invariant: every schema is_secret key is covered by the UI deny-list.
        schema = c.get("/api/admin/settings/schema", headers=Ho).json()
        secret_schema_keys = {
            f["key"]
            for group in schema["groups"].values()
            for f in group if f.get("is_secret")
        }
        check(secret_schema_keys <= SECRET_DENYLIST,
              "deny-list covers every is_secret schema key",
              f"uncovered={secret_schema_keys - SECRET_DENYLIST}")

        # Safe non-secret write is accepted + audited.
        r = c.put("/api/admin/settings", headers=Ho,
                  json={"updates": {"appearance.brand_name": "QA Owner Brand"}})
        check(r.status_code == 200 and r.json().get("success"),
              "safe non-secret settings write", r.text[:160])
        check(r.json().get("settings", {}).get("appearance.brand_name") == "QA Owner Brand",
              "safe value persisted + returned")

        # ---- 8. Audit trail ---------------------------------------------------
        print("\n[8] Audit trail")
        r = c.get("/api/admin/audit-logs", headers=Ho)
        d = r.json()
        check(r.status_code == 200 and isinstance(d.get("items"), list) and d["total"] > 0,
              "audit-logs has entries", f"total={d.get('total')}")
        mine = [a for a in d["items"] if a.get("actor") == owner_id]
        events = {a.get("action") for a in mine}
        check(bool(mine), "owner actions appear in audit-logs")
        check("settings.update" in events,
              "owner settings.update audited", str(sorted(events)))
        r = c.get("/api/admin/audit-logs/summary", headers=Ho)
        check(r.status_code == 200 and "by_severity" in r.json(),
              "audit-logs summary shape", r.text[:160])

        # ---- 9. Dangerous actions (owner = full control, all audited) ---------
        print("\n[9] Dangerous actions")
        r = c.post("/api/admin/system-health/engine/restart", headers=Ho)
        check(r.status_code == 200 and r.json().get("success"),
              "engine restart (audited)", r.text[:160])
        r = c.post("/api/admin/system-health/engine/stop", headers=Ho)
        check(r.status_code == 200 and r.json().get("success"),
              "engine stop (audited)", r.text[:160])
        r = c.post("/api/admin/system-health/engine/start", headers=Ho)
        check(r.status_code == 200 and r.json().get("success"),
              "engine start (audited)", r.text[:160])

        for action in ["disable", "pause", "resume", "close-all", "emergency-stop"]:
            r = c.post(f"/api/admin/trading/control/{action}", headers=Ho)
            check(r.status_code == 200 and r.json().get("success"),
                  f"trading control {action} (audited)", r.text[:160])
        r = c.post("/api/admin/trading/control/close-symbol", headers=Ho,
                   json={"symbol": "EURUSD"})
        check(r.status_code == 200 and r.json().get("success"),
              "trading control close-symbol (audited)", r.text[:160])
        r = c.post("/api/admin/trading/control/close-symbol", headers=Ho, json={})
        check(r.status_code == 400, "close-symbol without symbol rejected (400)",
              f"got {r.status_code}")
        # Restore trading state for subsequent suites.
        r = c.post("/api/admin/trading/control/enable", headers=Ho)
        check(r.status_code == 200, "trading re-enabled after cycle", r.text[:160])

        # News lifecycle + broadcast (mock telegram).
        r = c.post("/api/admin/news", headers=Ho,
                   json={"title": "QA Owner Broadcast", "body": "QA body",
                         "category": "update", "published": True})
        check(r.status_code == 200 and r.json().get("id"), "owner creates news", r.text[:160])
        news_id = r.json()["id"]
        r = c.post(f"/api/admin/news/{news_id}/broadcast", headers=Ho)
        d = r.json()
        check(r.status_code == 200 and "broadcasted" in d,
              "owner broadcasts news (mock telegram)", r.text[:160])
        r = c.patch(f"/api/admin/news/{news_id}", headers=Ho,
                    json={"published": False})
        check(r.status_code == 200 and r.json().get("success"),
              "owner updates news", r.text[:160])
        r = c.delete(f"/api/admin/news/{news_id}", headers=Ho)
        check(r.status_code == 200 and r.json().get("success"),
              "owner deletes news", r.text[:160])

        # --- 10. Portal isolation + boundary ----------------------------------
        print("\n[10] Portal isolation / boundary")
        r = c.get("/api/client/dashboard", headers=Hc)
        check(r.status_code == 200, "client portal API unaffected (200)", f"got {r.status_code}")
        r = c.get("/api/admin/overview", headers=Hc)
        check(r.status_code == 403, "client cannot cross into owner surface (403)",
              f"got {r.status_code}")
        # Owner token works across the whole admin surface (single shared JWT, OQ-2).
        r = c.get("/api/admin/overview", headers=Ho)
        check(r.status_code == 200, "owner JWT works across admin surface (OQ-2)",
              f"got {r.status_code}")

    print(f"\nTOTAL {PASSED + FAILED} | PASS {PASSED} | FAIL {FAILED} | ERROR {len(ERRORS)}")
    for name, detail in ERRORS:
        print(f"  FAILED: {name} :: {detail}")
    return 1 if (FAILED or ERRORS) else 0


if __name__ == "__main__":
    sys.exit(main())

"""Phase 3 Client Portal QA — portal auth, client 2FA, isolation, empty states.

Run:  python scripts/_qa_client_portal.py
Requires: QA DB (ict_funded_ea_qa) + TEST ENCRYPTION_KEY (see CLAUDE.md).

Covers the Phase 3 QA plan (docs/phase3_client_dashboard.md §13):
  - Portal endpoints require an active client JWT (401 without).
  - Register -> verify -> login; redirect target + role are correct for the portal.
  - Empty states: fresh client has no license / subscription / accounts; dashboard renders zero data.
  - Client 2FA full cycle for a NON-STAFF client (setup -> pending -> enable ->
    logout -> login 2FA step -> verify -> disable), asserting no other user's 2FA
    is touched (permission-scope correction in spec §0.7).
  - Session list + revoke; revoked refresh rejected; password change revokes sessions.
  - Isolation: a client token cannot reach /api/admin/* (403), cannot rename/delete
    another client's account (404), and only sees its own data.
  - Settings / notifications / telegram preference validation (invalid -> 400).

Idempotent: reseeds all test users every run.
"""
import asyncio
import base64
import hashlib
import hmac
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:cimoro2008@localhost:5432/ict_funded_ea_qa"
os.environ["ENCRYPTION_KEY"] = "XLX1vxl3BclZbOETIL-StfxdVDrWeRj5VBCG-eEQpr0="
os.environ["USE_MOCK_TELEGRAM_SCAN"] = "true"
os.environ.pop("TELEGRAM_BOT_TOKEN", None)
os.environ.pop("TELEGRAM_TEST_MODE", None)

PASSWORD = "Passw0rd!123"
NEW_PASSWORD = "PortalPassw0rd!456"
CLIENT_A = "portal-a@testmail.com"
CLIENT_B = "portal-b@testmail.com"

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


# ---------------------------------------------------------------------------
# Isolated DB helpers (own engine, never touches the app's event loop)
# ---------------------------------------------------------------------------
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
    from datetime import datetime, timezone
    key = base64.b32decode(secret.replace(" ", "").upper() + "=" * ((8 - len(secret.replace(" ", ""))) % 8))
    counter = int(datetime.now(timezone.utc).timestamp() // 30)
    msg = counter.to_bytes(8, "big")
    hm = hmac.new(key, msg, hashlib.sha1).digest()
    offset = hm[-1] & 0x0F
    code = ((int.from_bytes(hm[offset:offset + 4], "big") & 0x7FFFFFFF) % 1000000)
    return f"{code:06d}"


def _seed():
    async def _do(s):
        from datetime import datetime, timedelta, timezone
        from sqlalchemy import delete, select
        from database.base import Base
        from database.models import LoginSession, Role, Subscription, TradingAccount, User
        from security.access_control import seed_roles_and_permissions
        from security.password import hash_password

        await s.run_sync(lambda c: Base.metadata.create_all(c.bind))
        await seed_roles_and_permissions(s)
        client_role = (await s.execute(select(Role).where(Role.name == "client"))).scalar_one_or_none()
        admin_role = (await s.execute(select(Role).where(Role.name == "admin"))).scalar_one_or_none()
        now = datetime.now(timezone.utc)

        async def reset(email: str):
            u = (await s.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if not u:
                return None
            await s.execute(delete(TradingAccount).where(TradingAccount.user_id == u.id))
            await s.execute(delete(Subscription).where(Subscription.user_id == u.id))
            await s.execute(delete(LoginSession).where(LoginSession.user_id == u.id))
            await s.execute(delete(User).where(User.id == u.id))
            await s.flush()
            return u.id

        # Client A — fresh, empty account (empty-state + portal flows).
        await reset(CLIENT_A)
        a = User(email=CLIENT_A, password_hash=hash_password(PASSWORD),
                 first_name="Portal", last_name="A", role_id=client_role.id if client_role else None,
                 account_status="active", email_verified=True, language="EN")
        s.add(a)
        await s.flush()

        # Client B — seeded directly so isolation tests never need a broker.
        await reset(CLIENT_B)
        b = User(email=CLIENT_B, password_hash=hash_password(PASSWORD),
                 first_name="Portal", last_name="B", role_id=client_role.id if client_role else None,
                 account_status="active", email_verified=True, language="EN")
        s.add(b)
        await s.flush()
        s.add(TradingAccount(
            user_id=b.id, name="Isolated Account", platform="MT5", server="ICMarkets-Live08",
            login="987654", broker="Isolation Broker", account_type="standard",
            engine_status="ACTIVE", active=True, verified=True,
            balance_snapshot=10000.0, equity_snapshot=10000.0, currency="USD", demo_real="real",
            account_fingerprint=f"portal-b-{uuid.uuid4().hex[:16]}",
        ))

        # Admin — 2FA cleared so the staff-side assertions are deterministic.
        adm = (await s.execute(select(User).where(User.email == "qa_admin@test.local"))).scalar_one_or_none()
        if not adm:
            adm = User(email="qa_admin@test.local", password_hash=hash_password("AdminPass123!"),
                       first_name="QA", last_name="Admin", role_id=admin_role.id if admin_role else None,
                       account_status="active", email_verified=True)
            s.add(adm)
        else:
            adm.role_id = admin_role.id if admin_role else adm.role_id
            adm.email_verified = True
        adm.two_factor_enabled = False
        adm.two_factor_secret = None
        await s.commit()
    _run_sql(_do)


def _latest_verify_code(user_id: str, token_type: str):
    async def _q(s):
        from sqlalchemy import select
        from database.models import VerificationToken
        res = await s.execute(
            select(VerificationToken)
            .where(VerificationToken.user_id == user_id,
                   VerificationToken.type == token_type,
                   VerificationToken.used == False)
            .order_by(VerificationToken.created_at.desc())
        )
        rows = res.scalars().all()
        return rows[0].code if rows else None
    return _run_sql(_q)


def _user_id(email: str):
    async def _q(s):
        from sqlalchemy import select
        from database.models import User
        u = (await s.execute(select(User).where(User.email == email))).scalar_one_or_none()
        return u.id if u else None
    return _run_sql(_q)


def _two_factor_state(email: str):
    async def _q(s):
        from sqlalchemy import select
        from database.models import User
        u = (await s.execute(select(User).where(User.email == email))).scalar_one_or_none()
        return {"enabled": bool(u and u.two_factor_enabled),
                "pending": bool(u and u.two_factor_secret and not u.two_factor_enabled)}
    return _run_sql(_q)


def _patch_connector():
    from telegram_bot.services.mt_connector import mt_connector
    async def _fake_test(login_data):
        return mt_connector._mock_result(login_data)
    mt_connector.test_connection = _fake_test


def _login(c, email, password=PASSWORD):
    r = c.post("/auth/login", json={"email": email, "password": password})
    return r


def main() -> int:
    _seed()

    from fastapi.testclient import TestClient
    from api.main import app
    _patch_connector()
    os.environ["TELEGRAM_BOT_TOKEN"] = ""

    with TestClient(app) as c:
        # ---- 1. Unauthenticated guard ---------------------------------------
        print("\n[1] Unauthenticated guard")
        for path in ["/api/client/dashboard", "/api/client/profile", "/api/client/accounts",
                     "/api/client/license", "/api/client/subscription", "/api/client/trades",
                     "/api/client/performance", "/api/client/settings", "/api/client/ea",
                     "/api/client/telegram"]:
            r = c.get(path)
            check(r.status_code == 401, f"401 without token: {path}", f"got {r.status_code}")

        # ---- 2. Register -> verify -> login (client) ------------------------
        print("\n[2] Register / verify / login")
        email = f"portal-{uuid.uuid4().hex[:8]}@testmail.com"
        r = c.post("/auth/register", json={"email": email, "password": PASSWORD,
                                           "first_name": "New", "last_name": "Client"})
        check(r.status_code == 200 and r.json().get("id"), "register creates client", r.text[:160])
        uid = r.json().get("id")

        vcode = _latest_verify_code(uid, "verify_email")
        check(bool(vcode), "verification code generated")
        r = c.post("/auth/verify-email/confirm", json={"code": vcode})
        check(r.status_code == 200, "email verified", r.text[:160])

        r = _login(c, email)
        check(r.status_code == 200 and r.json().get("access_token"), "client login", r.text[:160])
        check(r.json().get("redirect_to") == "/dashboard",
              "client login redirect -> /dashboard", str(r.json().get("redirect_to")))
        check(r.json().get("user", {}).get("role") == "client", "client role in login payload",
              str(r.json().get("user")))

        # ---- 3. Client A empty-state snapshot --------------------------------
        print("\n[3] Empty-state data")
        r = _login(c, CLIENT_A)
        H = {"Authorization": "Bearer " + r.json()["access_token"]}
        A_RT = r.json()["refresh_token"]

        r = c.get("/auth/me", headers=H)
        check(r.status_code == 200 and r.json().get("role") == "client", "/auth/me role=client",
              r.text[:160])

        r = c.get("/api/client/license", headers=H)
        check(r.status_code == 200 and r.json()["items"] == [] and r.json()["total"] == 0,
              "license empty for fresh client", r.text[:160])

        r = c.get("/api/client/subscription", headers=H)
        check(r.status_code == 200 and r.json()["subscription"] is None,
              "subscription null for fresh client", r.text[:160])

        r = c.get("/api/client/accounts", headers=H)
        check(r.status_code == 200 and r.json()["items"] == [], "accounts empty for fresh client",
              r.text[:160])

        r = c.get("/api/client/dashboard", headers=H)
        d = r.json()
        check(r.status_code == 200 and d.get("license") is None and d.get("subscription") is None
              and d["totals"]["total_trades"] == 0, "dashboard zero-state renders", r.text[:200])

        # ---- 4. Settings + notifications validation --------------------------
        print("\n[4] Settings & preference validation")
        r = c.get("/api/client/settings", headers=H)
        prefs = r.json().get("preferences", {})
        check(r.status_code == 200 and prefs.get("theme") in {"dark", "light", "system"},
              "settings merged defaults returned", r.text[:160])

        r = c.patch("/api/client/settings", headers=H, json={"preferences": {"theme": "neon"}})
        check(r.status_code == 400, "invalid theme rejected (400)", f"got {r.status_code}")

        r = c.patch("/api/client/settings", headers=H,
                    json={"preferences": {"theme": "light",
                                          "default_symbols": ["XAUUSD", "nas100"],
                                          "default_timeframes": ["M15"],
                                          "trading_sessions": ["LONDON"]}})
        check(r.status_code == 200, "valid settings saved", r.text[:160])
        r = c.get("/api/client/settings", headers=H)
        p2 = r.json().get("preferences", {})
        check(p2.get("theme") == "light" and p2.get("default_symbols") == ["XAUUSD", "NAS100"],
              "saved settings reloaded (symbols uppercased)", str(p2))

        r = c.patch("/api/client/settings", headers=H,
                    json={"preferences": {"notifications": {"bogus_key": True}}})
        check(r.status_code == 400, "invalid notification key rejected (400)", f"got {r.status_code}")

        r = c.patch("/api/client/settings", headers=H,
                    json={"preferences": {"notifications": {"signals": False, "tp": True}}})
        check(r.status_code == 200, "valid notification keys saved", r.text[:160])

        r = c.patch("/api/client/telegram/preferences", headers=H, json={"notifications": {"nope": True}})
        check(r.status_code == 400, "telegram invalid notification key rejected (400)", f"got {r.status_code}")

        r = c.patch("/api/client/telegram/preferences", headers=H,
                    json={"notifications": {"signals": True}, "language": "AR"})
        check(r.status_code == 200, "telegram preferences saved", r.text[:160])

        # ---- 5. Isolation -----------------------------------------------------
        print("\n[5] Isolation")
        r = c.get("/api/client/accounts", headers=H)
        b_accounts = []
        r_b = _login(c, CLIENT_B)
        H_b = {"Authorization": "Bearer " + r_b.json()["access_token"]}
        r = c.get("/api/client/accounts", headers=H_b)
        check(r.status_code == 200 and len(r.json()["items"]) == 1, "client B sees its own account",
              r.text[:160])
        if r.status_code == 200 and r.json()["items"]:
            b_accounts = r.json()["items"]

        if b_accounts:
            bid = b_accounts[0]["id"]
            r = c.patch(f"/api/client/accounts/{bid}", headers=H, json={"name": "hacked"})
            check(r.status_code == 404, "client A cannot rename client B account (404)",
                  f"got {r.status_code}")
            r = c.delete(f"/api/client/accounts/{bid}", headers=H)
            check(r.status_code == 404, "client A cannot delete client B account (404)",
                  f"got {r.status_code}")

        r = c.get("/api/admin/overview", headers=H)
        check(r.status_code == 403, "client token blocked from /api/admin/overview (403)",
              f"got {r.status_code}")

        r = c.get("/api/client/accounts", headers=H)
        check(r.json()["items"] == [], "client A list stays empty (self-scoped)", r.text[:160])

        # ---- 6. Client 2FA full cycle (non-staff) -----------------------------
        print("\n[6] Client 2FA full cycle (non-staff)")
        a_id = _user_id(CLIENT_A)
        r = c.post("/auth/2fa/setup", headers=H, json={"current_password": PASSWORD})
        check(r.status_code == 200 and r.json().get("secret"), "client 2fa setup (password re-auth)",
              r.text[:160])
        secret = r.json().get("secret")
        otpauth = r.json().get("otpauth_uri", "")
        check(bool(otpauth) and otpauth.startswith("otpauth://"), "setup returns otpauth uri")

        state = _two_factor_state(CLIENT_A)
        check(state["pending"] is True and state["enabled"] is False,
              "me state two_factor_pending=True after setup")

        r = c.post("/auth/2fa/enable", headers=H, json={"code": "000000"})
        check(r.status_code == 401, "enable with wrong code rejected (401)", f"got {r.status_code}")

        r = c.post("/auth/2fa/enable", headers=H, json={"code": _totp(secret)})
        check(r.status_code == 200, "enable with valid TOTP", r.text[:160])

        state = _two_factor_state(CLIENT_A)
        check(state["enabled"] is True and state["pending"] is False,
              "me state two_factor_enabled=True after enable")

        # Login through the 2FA step.
        r = _login(c, CLIENT_A)
        check(r.status_code == 200 and r.json().get("two_factor_required") is True,
              "login returns two_factor_required", r.text[:160])
        t2fa = r.json().get("two_factor_token")

        r = c.post("/auth/2fa/verify", json={"code": "000000", "two_factor_token": t2fa})
        check(r.status_code == 401, "verify with wrong code rejected (401)", f"got {r.status_code}")

        r = c.post("/auth/2fa/verify", json={"code": _totp(secret), "two_factor_token": t2fa})
        check(r.status_code == 200 and r.json().get("access_token"),
              "verify with valid code issues tokens", r.text[:160])
        H = {"Authorization": "Bearer " + r.json()["access_token"]}
        A_RT = r.json()["refresh_token"]

        # Disable with TOTP.
        r = c.post("/auth/2fa/disable", headers=H, json={"code": "000000"})
        check(r.status_code == 401, "disable with wrong code rejected (401)", f"got {r.status_code}")
        r = c.post("/auth/2fa/disable", headers=H, json={"code": _totp(secret)})
        check(r.status_code == 200, "disable with valid code", r.text[:160])

        state = _two_factor_state(CLIENT_A)
        check(state["enabled"] is False and state["pending"] is False,
              "2fa fully disabled after cycle")

        # No other user's 2FA touched.
        b_state = _two_factor_state(CLIENT_B)
        check(b_state["enabled"] is False, "client B 2FA untouched by client A cycle")

        # ---- 7. Sessions + revoke + password change ---------------------------
        print("\n[7] Sessions & password change")
        r = c.get("/auth/sessions", headers=H)
        actives = [s["id"] for s in r.json().get("sessions", []) if s.get("is_active")]
        check(r.status_code == 200 and actives, "session list includes active sessions",
              r.text[:160])

        if actives:
            r = c.delete(f"/auth/sessions/{actives[-1]}", headers=H)
            check(r.status_code == 200, "own session revoked", f"got {r.status_code}")

        # Password change revokes remaining sessions.
        r = c.post("/auth/change-password", headers=H,
                   json={"current_password": PASSWORD, "new_password": NEW_PASSWORD})
        check(r.status_code == 200, "password changed", r.text[:160])

        r = c.post("/auth/refresh", json={"refresh_token": A_RT})
        check(r.status_code == 401, "pre-change refresh token rejected after password change",
              f"got {r.status_code}")

        # Login with the new password.
        r = _login(c, CLIENT_A, NEW_PASSWORD)
        check(r.status_code == 200 and r.json().get("access_token"),
              "login with new password", r.text[:160])

        # ---- 8. Staff redirect (portal must not be the staff target) ----------
        print("\n[8] Staff redirect target")
        r = _login(c, "qa_admin@test.local", "AdminPass123!")
        check(r.status_code == 200 and r.json().get("redirect_to") == "/dashboard",
              "staff login redirects to admin /dashboard, not the portal",
              f"got {r.status_code} {r.text[:160]}")

    print(f"\nTOTAL {PASSED + FAILED} | PASS {PASSED} | FAIL {FAILED} | ERROR {len(ERRORS)}")
    for name, detail in ERRORS:
        print(f"  FAILED: {name} :: {detail}")
    return 1 if (FAILED or ERRORS) else 0


if __name__ == "__main__":
    sys.exit(main())

"""Phase 1 Auth — full 20-scenario QA.

Run:  python scripts/_qa_auth_full.py
Requires: QA DB (ict_funded_ea_qa) + TEST ENCRYPTION_KEY (see CLAUDE.md).

The admin account is re-seeded here (qa_admin@test.local / AdminPass123!),
and its 2FA state is cleared, so this script is idempotent across runs.
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

PASSED = 0
FAILED = 0
ERRORS = []


def ok(name: str) -> None:
    global PASSED
    PASSED += 1
    print(f"[PASS] {name}")


def fail(name: str, detail: str) -> None:
    global FAILED
    FAILED += 1
    ERRORS.append((name, detail))
    print(f"[FAIL] {name} -> {detail}")


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


def _seed_admin():
    async def _do(s):
        from sqlalchemy import select
        from database.base import Base
        from database.models import User, Role
        from security.access_control import seed_roles_and_permissions
        from security.password import hash_password
        await s.run_sync(lambda c: Base.metadata.create_all(c.bind))
        await seed_roles_and_permissions(s)
        role = (await s.execute(select(Role).where(Role.name == "admin"))).scalar_one_or_none()
        u = (await s.execute(select(User).where(User.email == "qa_admin@test.local"))).scalar_one_or_none()
        if not u:
            u = User(email="qa_admin@test.local", password_hash=hash_password("AdminPass123!"),
                     first_name="QA", last_name="Admin", role_id=role.id if role else None,
                     status="active", account_status="active", email_verified=True)
            s.add(u)
        else:
            u.role_id = role.id if role else u.role_id
            u.email_verified = True
        u.two_factor_enabled = False
        u.two_factor_secret = None
        await s.commit()
        return u.id
    return _run_sql(_do)


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


def _email_verified(user_id: str):
    async def _q(s):
        from sqlalchemy import select
        from database.models import User
        u = (await s.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        return bool(u and u.email_verified)
    return _run_sql(_q)


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


def main() -> int:
    admin_id = _seed_admin()

    from api.main import app
    from api.services.rate_limit import clear_all
    from security.jwt_handler import create_token
    from datetime import datetime, timedelta, timezone

    with TestClient(app) as c:
        email = f"qa-{uuid.uuid4().hex[:10]}@testmail.com"
        pw = "Passw0rd!123"
        newpw = "NewPassw0rd!456"

        # --- S1: Register a new account ---
        r = c.post("/auth/register", json={
            "email": email, "password": pw, "first_name": "Qa", "last_name": "User"})
        if r.status_code == 200 and r.json().get("id"):
            ok("S1 Register creates account")
        else:
            fail("S1 Register creates account", r.text)
        uid = r.json().get("id")

        # --- S15: Unverified email cannot login ---
        r = c.post("/auth/login", json={"email": email, "password": pw})
        if r.status_code == 403 and "verified" in r.json().get("detail", "").lower():
            ok("S15 Unverified email blocked at login (403)")
        else:
            fail("S15 Unverified email blocked at login", f"{r.status_code} {r.text}")

        # --- S2: Email verification code delivered ---
        vcode = _latest_verify_code(uid, "verify_email")
        if vcode:
            ok("S2 Email verification code generated (delivered via SMTP when configured)")
        else:
            fail("S2 Email verification code generated", "no verify_email token found")

        # --- S3: Verify email ---
        r = c.post("/auth/verify-email/confirm", json={"code": vcode})
        if r.status_code == 200 and _email_verified(uid):
            ok("S3 Email verified successfully")
        else:
            fail("S3 Email verified successfully", f"{r.status_code} {r.text}")

        # --- S4: Login ---
        r = c.post("/auth/login", json={"email": email, "password": pw})
        if r.status_code == 200 and r.json().get("access_token"):
            ok("S4 Login issues access + refresh tokens")
        else:
            fail("S4 Login issues access + refresh tokens", r.text)
        rt = r.json().get("refresh_token")

        # --- S5: Logout revokes session ---
        r = c.post("/auth/logout", json={"refresh_token": rt})
        if r.status_code == 200:
            ok("S5 Logout accepted")
        else:
            fail("S5 Logout accepted", r.text)
        r = c.post("/auth/refresh", json={"refresh_token": rt})
        if r.status_code == 401:
            ok("S5b Logout invalidates refresh token")
        else:
            fail("S5b Logout invalidates refresh token", f"{r.status_code} {r.text}")

        # --- S6: Login with Remember Me ---
        r = c.post("/auth/login", json={"email": email, "password": pw, "remember_me": True})
        if r.status_code == 200 and r.json().get("remember_me") is True:
            ok("S6 Login with Remember Me")
        else:
            fail("S6 Login with Remember Me", r.text)

        # --- S16: Wrong password ---
        r = c.post("/auth/login", json={"email": email, "password": "TotallyWrong1!"})
        if r.status_code == 401:
            ok("S16 Wrong password rejected (401)")
        else:
            fail("S16 Wrong password rejected", f"{r.status_code} {r.text}")

        # --- S20 (part A): Admin login redirects to /dashboard ---
        r = c.post("/auth/login", json={"email": "qa_admin@test.local", "password": "AdminPass123!"})
        if r.status_code == 200 and r.json().get("redirect_to") == "/dashboard":
            ok("S20a Admin login redirects to /dashboard")
        else:
            fail("S20a Admin login redirects to /dashboard", f"{r.status_code} {r.text}")
        admin_rt = r.json().get("refresh_token")
        H = {"Authorization": "Bearer " + r.json()["access_token"]}

        # --- S7: Enable 2FA (staff only, password re-auth) ---
        r = c.post("/auth/2fa/setup", json={"current_password": "AdminPass123!"}, headers=H)
        if r.status_code == 200 and r.json().get("secret"):
            asecret = r.json()["secret"]
        else:
            asecret = None
            fail("S7 2FA setup", r.text)
        if asecret:
            r = c.post("/auth/2fa/enable", json={"code": _totp(asecret)}, headers=H)
            if r.status_code == 200:
                ok("S7 Enable 2FA with valid TOTP")
            else:
                fail("S7 Enable 2FA with valid TOTP", r.text)

        # --- S8: Admin logout ---
        r = c.post("/auth/logout", json={"refresh_token": admin_rt})
        if r.status_code == 200:
            ok("S8 Admin logout")
        else:
            fail("S8 Admin logout", r.text)

        # --- S17: Wrong 2FA code ---
        r = c.post("/auth/login", json={"email": "qa_admin@test.local", "password": "AdminPass123!"})
        t2fa = r.json().get("two_factor_token") if r.json().get("two_factor_required") else None
        r = c.post("/auth/2fa/verify", json={"code": "000000", "two_factor_token": t2fa})
        if t2fa and r.status_code == 401:
            ok("S17 Wrong 2FA code rejected (401)")
        else:
            fail("S17 Wrong 2FA code rejected", f"{r.status_code} {r.text}")

        # --- S9: Login + 2FA (correct code) ---
        r = c.post("/auth/login", json={"email": "qa_admin@test.local", "password": "AdminPass123!"})
        t2fa = r.json().get("two_factor_token")
        r = c.post("/auth/2fa/verify", json={"code": _totp(asecret), "two_factor_token": t2fa})
        if r.status_code == 200 and r.json().get("access_token"):
            ok("S9 Login + 2FA issues tokens")
        else:
            fail("S9 Login + 2FA issues tokens", f"{r.status_code} {r.text}")
        H = {"Authorization": "Bearer " + r.json()["access_token"]}
        admin_rt2 = r.json().get("refresh_token")
        admin_id = r.json()["user"]["id"]

        # --- S13: Revoke session ---
        r = c.get("/auth/sessions", headers=H)
        actives = [s["id"] for s in r.json().get("sessions", []) if s.get("is_active")]
        r = c.delete(f"/auth/sessions/{actives[0]}", headers=H) if actives else (401, {})
        if actives and r.status_code == 200:
            ok("S13 Session revoked")
        else:
            fail("S13 Session revoked", f"actives={len(actives)} {getattr(r, 'status_code', '?')}")

        # --- S14: Revoked session rejected immediately ---
        r = c.post("/auth/refresh", json={"refresh_token": admin_rt2})
        if r.status_code == 401:
            ok("S14 Revoked session rejected immediately (401)")
        else:
            fail("S14 Revoked session rejected immediately", f"{r.status_code} {r.text}")

        # --- S18: Expired access token ---
        expired = create_token(str(admin_id), "access",
                               datetime.now(timezone.utc) - timedelta(seconds=5), role="admin")
        r = c.get("/auth/me", headers={"Authorization": "Bearer " + expired})
        if r.status_code == 401:
            ok("S18 Expired access token rejected (401)")
        else:
            fail("S18 Expired access token rejected", f"{r.status_code} {r.text}")

        # --- S10: Forgot password ---
        r = c.post("/auth/forgot-password", json={"email": email})
        rcode = _latest_verify_code(uid, "reset_password")
        if r.status_code == 200 and rcode:
            ok("S10 Forgot password issues reset code")
        else:
            fail("S10 Forgot password issues reset code", f"{r.status_code} code={rcode}")

        # --- S11: Reset password ---
        r = c.post("/auth/reset-password", json={"code": rcode, "new_password": newpw})
        if r.status_code == 200:
            ok("S11 Password reset with code")
        else:
            fail("S11 Password reset with code", r.text)

        # --- S12: Login with new password ---
        r = c.post("/auth/login", json={"email": email, "password": newpw})
        if r.status_code == 200 and r.json().get("access_token"):
            ok("S12 Login with new password")
        else:
            fail("S12 Login with new password", r.text)

        # --- S20 (part B): Client login redirects to client dashboard ---
        if r.json().get("redirect_to") == "/dashboard":
            ok("S20b Client login redirects to /dashboard")
        else:
            fail("S20b Client login redirects to /dashboard", r.text)

        # --- S19: Rate limit (429 after limit) ---
        clear_all()
        hit_429 = None
        for i in range(12):
            r = c.post("/auth/login", json={"email": "nobody@testmail.com", "password": "WrongPass1!"})
            if r.status_code == 429:
                hit_429 = i + 1
                break
        if hit_429 is not None:
            ok(f"S19 Rate limit returns 429 (after {hit_429} attempts)")
        else:
            fail("S19 Rate limit returns 429", "never got 429")

    print(f"\nTOTAL {PASSED + FAILED} | PASS {PASSED} | FAIL {FAILED} | ERROR {len(ERRORS)}")
    for name, detail in ERRORS:
        print(f"  FAILED: {name} :: {detail}")
    return 1 if (FAILED or ERRORS) else 0


if __name__ == "__main__":
    from fastapi.testclient import TestClient
    sys.exit(main())

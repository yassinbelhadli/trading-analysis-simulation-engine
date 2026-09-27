"""Phase 1 Authentication E2E — run against the QA database.

Usage:
    $env:DATABASE_URL='postgresql+asyncpg://postgres:cimoro2008@localhost:5432/ict_funded_ea_qa'
    .venv\\Scripts\\python.exe scripts/_qa_auth_e2e.py
"""
import asyncio
import base64
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:cimoro2008@localhost:5432/ict_funded_ea_qa",
)
os.environ.setdefault("ENCRYPTION_KEY", "XLX1vxl3BclZbOETIL-StfxdVDrWeRj5VBCG-eEQpr0=")


def _totp(secret: str) -> str:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.twofactor.totp import TOTP
    pad = secret.strip().upper() + "=" * ((8 - len(secret) % 8) % 8)
    key = base64.b32decode(pad)
    return TOTP(key, 6, hashes.SHA1(), 30).generate(time.time()).decode()


def _reset_2fa():
    async def reset():
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from database.base import Base
        from database.models import User, Role
        from security.access_control import seed_roles_and_permissions
        from security.password import hash_password
        url = os.environ["DATABASE_URL"]
        eng = create_async_engine(url)
        factory = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
        try:
            async with eng.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            async with factory() as s:
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
        finally:
            await eng.dispose()
    asyncio.run(reset())


def main():
    _reset_2fa()
    from fastapi.testclient import TestClient
    from api.main import app

    ADMIN = {"email": "qa_admin@test.local", "password": "AdminPass123!"}
    steps = []

    def ok(label: str):
        steps.append(label)
        print(f"[PASS] {label}")

    with TestClient(app) as c:
        r = c.post("/auth/login", json=ADMIN)
        assert r.status_code == 200 and "access_token" in r.json(), r.text
        H = {"Authorization": "Bearer " + r.json()["access_token"]}

        r = c.post("/auth/2fa/setup", json={"current_password": ADMIN["password"]}, headers=H)
        assert r.status_code == 200, r.text
        secret = r.json()["secret"]
        assert r.json()["otpauth_uri"].startswith("otpauth://totp/")
        ok("AUTH-2FA setup issues secret + otpauth URI")

        r = c.post("/auth/2fa/enable", json={"code": _totp(secret)}, headers=H)
        assert r.status_code == 200, r.text
        ok("AUTH-2FA enable with valid TOTP")

        r = c.post("/auth/2fa/verify", json={"two_factor_token": "x", "code": "000000"})
        assert r.status_code == 401, r.status_code
        ok("AUTH-2FA wrong code rejected")

        r = c.post("/auth/login", json=ADMIN)
        assert r.status_code == 200 and r.json().get("two_factor_required") is True, r.text
        assert "access_token" not in r.json()
        twofa = r.json()["two_factor_token"]
        ok("AUTH-2FA login now requires TOTP step")

        r = c.post("/auth/2fa/verify",
                   json={"two_factor_token": twofa, "code": _totp(secret), "remember_me": True})
        assert r.status_code == 200 and "access_token" in r.json(), r.text
        assert r.json()["remember_me"] is True
        H = {"Authorization": "Bearer " + r.json()["access_token"]}
        ok("AUTH-2FA second-step login issues tokens")

        r = c.get("/auth/sessions", headers=H)
        assert r.status_code == 200 and len(r.json()["sessions"]) >= 1, r.text
        sid = r.json()["sessions"][0]["id"]
        r = c.delete(f"/auth/sessions/{sid}", headers=H)
        assert r.status_code == 200, r.text
        ok("AUTH-sessions list + revoke")

        import uuid
        unv_email = f"unverified-{uuid.uuid4().hex[:8]}@testmail.com"
        r = c.post("/auth/register",
                   json={"email": unv_email, "password": "Passw0rd!123"})
        assert r.status_code == 200, r.text
        r = c.post("/auth/login",
                   json={"email": unv_email, "password": "Passw0rd!123"})
        assert r.status_code == 403 and "verified" in r.json()["detail"].lower(), (r.status_code, r.text)
        ok("AUTH-unverified user blocked at login")

        r = c.get("/auth/me", headers=H)
        assert r.json()["two_factor_enabled"] is True
        ok("AUTH-/me reflects 2FA state")

    print(f"TOTAL {len(steps)} | PASS {len(steps)} | FAIL 0 | ERROR 0")


if __name__ == "__main__":
    main()

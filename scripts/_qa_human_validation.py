"""Human Validation Kit QA — demo seed idempotency, 3-role logins,
email_verified behaviour (EMAIL_TEST_MODE dev mailbox), role isolation,
auth + RBAC regression, and no-production-config-change checks.

Run:  python scripts/_qa_human_validation.py
Requires: DEV database (ict_funded_ea) + TEST ENCRYPTION_KEY (see CLAUDE.md).

Deliberately runs against the DEV database because the demo seed targets it.
Idempotent: the seed is re-run (not destructive) and any throwaway user
created by this script is deleted at the end.
"""
import asyncio
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:cimoro2008@localhost:5432/ict_funded_ea"
os.environ["ENCRYPTION_KEY"] = "XLX1vxl3BclZbOETIL-StfxdVDrWeRj5VBCG-eEQpr0="
os.environ["USE_MOCK_TELEGRAM_SCAN"] = "true"
os.environ["TELEGRAM_BOT_TOKEN"] = ""
os.environ.pop("TELEGRAM_TEST_MODE", None)
os.environ.pop("EMAIL_TEST_MODE", None)  # prove default-off first

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


def _count_demo_rows(table: str, user_id: str) -> int:
    async def _q(s):
        from sqlalchemy import select, text
        r = await s.execute(
            text(f"SELECT count(*) FROM {table} WHERE user_id = :uid"),
            {"uid": user_id},
        )
        return int(r.scalar() or 0)
    return _run_sql(_q)


def _user_row(email: str):
    async def _q(s):
        from sqlalchemy import select
        from database.models import User
        u = (await s.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if not u:
            return None
        return {"id": u.id, "email": u.email, "email_verified": u.email_verified,
                "role": u.role_rel.name if u.role_rel else None}
    return _run_sql(_q)


def _delete_user_rows(user_id: str):
    async def _q(s):
        from sqlalchemy import delete
        from database.models import AuditLog, LoginSession, Subscription, TradingAccount, User, VerificationToken
        await s.execute(delete(VerificationToken).where(VerificationToken.user_id == user_id))
        await s.execute(delete(LoginSession).where(LoginSession.user_id == user_id))
        await s.execute(delete(TradingAccount).where(TradingAccount.user_id == user_id))
        await s.execute(delete(Subscription).where(Subscription.user_id == user_id))
        await s.execute(delete(AuditLog).where(AuditLog.user_id == user_id))
        await s.execute(delete(User).where(User.id == user_id))
        await s.commit()
    _run_sql(_q)


def _config_env_flag(name: str) -> str | None:
    from dotenv import dotenv_values
    return dotenv_values(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                      "config", ".env")).get(name)


def _config_snapshot() -> dict:
    from pathlib import Path
    cfg = Path(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config"))
    return {p.name: p.stat().st_mtime_ns for p in sorted(cfg.iterdir()) if p.is_file()}


def main() -> int:
    from api.services.email_test_mode import (
        clear_dev_mailbox,
        is_email_test_mode_enabled,
        read_dev_mailbox,
    )

    # ---- 0. Preconditions -------------------------------------------------
    print("\n[0] Preconditions")
    check(_config_env_flag("EMAIL_TEST_MODE") not in ("1", "true", "yes"),
          "EMAIL_TEST_MODE not persisted in config/.env",
          f"value={_config_env_flag('EMAIL_TEST_MODE')!r}")
    check(not is_email_test_mode_enabled(),
          "EMAIL_TEST_MODE disabled by default",
          f"enabled={is_email_test_mode_enabled()}")
    cfg_before = _config_snapshot()

    # ---- 1. Seed idempotency ----------------------------------------------
    print("\n[1] Demo seed idempotency (dev DB)")
    from scripts.seed_demo import DEMO_ADMIN_EMAIL, DEMO_CLIENT_EMAIL, DEMO_OWNER_EMAIL, seed as seed_demo

    summary1 = asyncio.run(seed_demo())
    summary2 = asyncio.run(seed_demo())

    check(summary1 == summary2, "second seed run produced identical counts", f"{summary1} vs {summary2}")
    for key in ["licenses", "subscriptions", "accounts", "scans",
                "risk_profiles", "tickets", "news", "news_events",
                "ea_builds", "site_settings"]:
        check(summary1.get(key, 0) >= 1, f"seeded non-zero: {key}", str(summary1.get(key)))
    check(summary1["total_users"] >= 3, ">=3 users in dev DB", str(summary1["total_users"]))

    owner = _user_row(DEMO_OWNER_EMAIL)
    admin = _user_row(DEMO_ADMIN_EMAIL)
    client = _user_row(DEMO_CLIENT_EMAIL)
    check(bool(owner and owner["role"] == "owner" and owner["email_verified"]),
          "demo owner exists, role=owner, email_verified=True", str(owner))
    check(bool(admin and admin["role"] == "admin" and admin["email_verified"]),
          "demo admin exists, role=admin, email_verified=True", str(admin))
    check(bool(client and client["role"] == "client" and client["email_verified"]),
          "demo client exists, role=client, email_verified=True", str(client))

    # Demo-scoped rows exist in the DB (creation counters are 0 on an
    # already-seeded dev DB — that is the point of idempotency).
    demo_trades = _count_demo_rows("paper_trades", client["id"])
    demo_audit = _count_demo_rows("audit_logs", client["id"])
    check(demo_trades >= 12, ">=12 demo paper trades in dev DB", str(demo_trades))
    check(demo_audit >= 7, ">=7 client-scoped demo audit rows in dev DB", str(demo_audit))

    # ---- 2. RBAC regression ------------------------------------------------
    print("\n[2] Auth + RBAC regression")
    def _roles_ok():
        async def _q(s):
            from sqlalchemy import select
            from database.models import Role
            rows = (await s.execute(select(Role))).scalars().all()
            names = {r.name for r in rows}
            return {"owner", "admin", "client", "support"} <= names, sorted(names)
        return _run_sql(_q)
    roles_ok, role_names = _roles_ok()
    check(roles_ok, "built-in roles still seeded", ",".join(role_names))

    # ---- 3. Logins ----------------------------------------------------------
    print("\n[3] Three-role login (email_verified demo users)")
    from fastapi.testclient import TestClient
    from api.main import app

    with TestClient(app) as c:
        for label, email, password, expected_role, expected_redirect in [
            ("owner", DEMO_OWNER_EMAIL, "OwnerDemo!2026", "owner", "/dashboard"),
            ("admin", DEMO_ADMIN_EMAIL, "AdminDemo!2026", "admin", "/dashboard"),
            ("client", DEMO_CLIENT_EMAIL, "ClientDemo!2026", "client", "/dashboard"),
        ]:
            r = c.post("/auth/login", json={"email": email, "password": password})
            body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            check(r.status_code == 200, f"login {label} -> 200", f"got {r.status_code}: {r.text[:160]}")
            check(body.get("user", {}).get("role") == expected_role, f"login {label} role", str(body.get("user", {}).get("role")))
            check(body.get("redirect_to") == expected_redirect, f"login {label} redirect_to", str(body.get("redirect_to")))

        r = c.post("/auth/login", json={"email": DEMO_CLIENT_EMAIL, "password": "WrongPass!123"})
        check(r.status_code == 401, "wrong password rejected 401", str(r.status_code))

        # ---- 4. email_verified behaviour -------------------------------------
        print("\n[4] email_verified behaviour (EMAIL_TEST_MODE)")
        # 4a. Default off: register -> code created. When real SMTP is configured
        # the email actually sends so verification_sent=True; when SMTP is not
        # configured (dev) it returns False.
        temp1 = f"hvk-off-{uuid.uuid4().hex[:8]}@testmail.com"
        r = c.post("/auth/register", json={"email": temp1, "password": "TempPass!123",
                                           "first_name": "Temp", "last_name": "One"})
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        check(r.status_code == 200, "register temp1 -> 200", r.text[:160])
        smtp_configured = bool((os.environ.get("SMTP_USER") or os.environ.get("SMTP_USERNAME") or "").strip()
                               and (os.environ.get("SMTP_PASS") or "").strip())
        expected_sent = True if smtp_configured else False
        check(body.get("verification_sent") is expected_sent,
              f"EMAIL_TEST_MODE off -> verification_sent={expected_sent}",
              str(body.get("verification_sent")))
        if not smtp_configured:
            check(read_dev_mailbox(to=temp1) == [],
                  "no dev mailbox record while EMAIL_TEST_MODE off", "records found")
        r = c.post("/auth/login", json={"email": temp1, "password": "TempPass!123"})
        if smtp_configured:
            # SMTP sends, so login is blocked for unverified but code was delivered
            check(r.status_code == 403,
                  "unverified user login -> 403 (SMTP configured)",
                  f"{r.status_code}: {r.text[:160]}")
        else:
            check(r.status_code == 403 and "could not send" in r.json().get("detail", "").lower(),
                  "unverified user login -> 403, code could not be sent",
                  f"{r.status_code}: {r.text[:160]}")

        # 4b. EMAIL_TEST_MODE on: full register -> mailbox -> verify -> login.
        # Temporarily remove real SMTP creds from env so test mode activates.
        saved_smtp_user = os.environ.pop("SMTP_USER", None)
        saved_smtp_pass = os.environ.pop("SMTP_PASS", None)
        saved_smtp_username = os.environ.pop("SMTP_USERNAME", None)
        os.environ["EMAIL_TEST_MODE"] = "true"
        check(is_email_test_mode_enabled(), "EMAIL_TEST_MODE now enabled", "")
        clear_dev_mailbox()

        temp2 = f"hvk-on-{uuid.uuid4().hex[:8]}@testmail.com"
        r = c.post("/auth/register", json={"email": temp2, "password": "TempPass!123",
                                           "first_name": "Temp", "last_name": "Two"})
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        check(body.get("verification_sent") is True,
              "EMAIL_TEST_MODE on -> verification_sent=True", str(body.get("verification_sent")))

        r = c.post("/auth/login", json={"email": temp2, "password": "TempPass!123"})
        check(r.status_code == 403 and "sent to your email" in r.json().get("detail", ""),
              "unverified user login -> 403, code was sent (via mailbox)",
              f"{r.status_code}: {r.text[:160]}")

        # The login attempt marks the register-time code used and issues a NEW
        # one — read the mailbox AFTER login so the newest code is valid.
        records = read_dev_mailbox(to=temp2, kind="verify_email")
        check(len(records) >= 1 and records[0].get("code"),
              "dev mailbox holds a fresh verify_email code after login", str(records[0].get("code") if records else None))

        code = records[0]["code"]
        r = c.post("/auth/verify-email/confirm", json={"code": code})
        check(r.status_code == 200, "verify-email/confirm with mailbox code -> 200", r.text[:160])

        r = c.post("/auth/login", json={"email": temp2, "password": "TempPass!123"})
        check(r.status_code == 200 and r.json().get("redirect_to") == "/dashboard",
              "verified temp user logs in -> /dashboard", f"{r.status_code}: {r.text[:160]}")

        # 4c. Forgot password -> reset code lands in dev mailbox.
        r = c.post("/auth/forgot-password", json={"email": DEMO_CLIENT_EMAIL})
        check(r.status_code == 200, "forgot-password demo client -> 200", r.text[:160])
        resets = read_dev_mailbox(to=DEMO_CLIENT_EMAIL, kind="reset_password")
        check(len(resets) == 1 and resets[0].get("code"),
              "dev mailbox holds reset_password code for demo client",
              str(resets[0].get("code") if resets else None))

        # ---- 5. Isolation ----------------------------------------------------
        # Restore SMTP env vars after EMAIL_TEST_MODE section.
        if saved_smtp_user is not None:
            os.environ["SMTP_USER"] = saved_smtp_user
        if saved_smtp_pass is not None:
            os.environ["SMTP_PASS"] = saved_smtp_pass
        if saved_smtp_username is not None:
            os.environ["SMTP_USERNAME"] = saved_smtp_username
        os.environ.pop("EMAIL_TEST_MODE", None)
        print("\n[5] Role isolation (client <-> admin <-> owner)")

        def _token(email: str, password: str) -> str:
            resp = c.post("/auth/login", json={"email": email, "password": password})
            return resp.json()["access_token"]

        def _get(token: str, path: str):
            return c.get(path, headers={"Authorization": f"Bearer {token}"})

        ct = _token(DEMO_CLIENT_EMAIL, "ClientDemo!2026")
        at = _token(DEMO_ADMIN_EMAIL, "AdminDemo!2026")
        ot = _token(DEMO_OWNER_EMAIL, "OwnerDemo!2026")

        r = _get(ct, "/api/admin/overview")
        check(r.status_code == 403, "client token -> /api/admin/overview 403", str(r.status_code))
        r = _get(ct, "/api/admin/clients")
        check(r.status_code == 403, "client token -> /api/admin/clients 403", str(r.status_code))
        r = _get(at, "/api/admin/overview")
        check(r.status_code == 200, "admin token -> /api/admin/overview 200", str(r.status_code))
        r = _get(ot, "/api/admin/overview")
        check(r.status_code == 200, "owner token -> /api/admin/overview 200", str(r.status_code))
        r = _get(ct, "/api/client/dashboard")
        check(r.status_code == 200, "client token -> /api/client/dashboard 200", str(r.status_code))
        r = c.get("/api/client/dashboard")
        check(r.status_code == 401, "no token -> /api/client/dashboard 401", str(r.status_code))

        # ---- 6. No production config changes ---------------------------------
        print("\n[6] No production config changes")
        cfg_after = _config_snapshot()
        check(cfg_before == cfg_after, "config/ directory untouched (mtime snapshot)",
              f"before={cfg_before} after={cfg_after}")
        check(_config_env_flag("EMAIL_TEST_MODE") not in ("1", "true", "yes"),
              "EMAIL_TEST_MODE not persisted in config/.env after run", "")

        # ---- Cleanup ----------------------------------------------------------
        print("\n[cleanup] removing throwaway QA users")
        u1 = _user_row(temp1)
        u2 = _user_row(temp2)
        if u1:
            _delete_user_rows(u1["id"])
        if u2:
            _delete_user_rows(u2["id"])
        check(_user_row(temp1) is None and _user_row(temp2) is None,
              "throwaway QA users removed from dev DB", "")

    print(f"\n=== RESULT: {PASSED} passed, {FAILED} failed ===")
    if ERRORS:
        print("\nFailures:")
        for name, detail in ERRORS:
            print(f"  - {name}: {detail}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())

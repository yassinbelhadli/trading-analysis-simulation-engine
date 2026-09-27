"""Phase 6.0 Foundations QA — notification pipeline skeleton + system-health
integrations + permission-gated delivery endpoints.

Run:  python scripts/_qa_notifications.py
Requires: QA DB (ict_funded_ea_qa) + TEST ENCRYPTION_KEY (see CLAUDE.md).

Covers:
  - Notification pipeline: preferences normalization, rule resolution (user
    toggles gate Telegram), template rendering (AR/EN/FR/ES), channel mock
    delivery (TELEGRAM_TEST_MODE / EMAIL_TEST_MODE), dispatch + broadcast audit
    records (persisted delivery log via audit_logs — no schema change).
  - System-health integrations: GET /api/admin/system-health/integrations shape
    and access control; honest restart status (supported=false).
  - Permission-gated endpoints: emails.read / emails.send / telegram.send are
    now real, audited surface (401 unauth / 403 client / 200 owner+admin).

Idempotent: reseeds all fixture users every run.
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:cimoro2008@localhost:5432/ict_funded_ea_qa"
os.environ["ENCRYPTION_KEY"] = "XLX1vxl3BclZbOETIL-StfxdVDrWeRj5VBCG-eEQpr0="
os.environ["USE_MOCK_TELEGRAM_SCAN"] = "true"
os.environ["TELEGRAM_TEST_MODE"] = "true"
os.environ["EMAIL_TEST_MODE"] = "true"

PASSWORD = "PortalPassw0rd!456"
OWNER = "qa_notif_owner@test.local"
ADMIN = "qa_notif_admin@test.local"
CLIENT = "qa_notif_client@test.local"

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


def _run_async(fn):
    return asyncio.run(fn())


def _seed():
    async def _do(s):
        from sqlalchemy import delete, select
        from database.base import Base
        from database.models import (
            AccountScan, AuditLog, License, LoginSession, PaperTrade, RiskProfile, Role,
            Subscription, SupportTicket, TicketMessage, TradingAccount, User,
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
        }

        def _user(email, role_name, first, last, telegram_id=None, language="EN", preferences=None):
            return User(
                email=email,
                password_hash=hash_password(PASSWORD),
                role_id=roles.get(role_name),
                account_status="active",
                email_verified=True,
                first_name=first, last_name=last,
                telegram_id=telegram_id, language=language,
                preferences=preferences,
            )

        s.add(_user(OWNER, "owner", "QA", "Owner"))
        s.add(_user(ADMIN, "admin", "QA", "Admin"))
        s.add(_user(CLIENT, "client", "QA", "Client"))
        s.add(_user("qa_notif_on@test.local", "client", "QA", "NotifOn",
                    telegram_id=100000001, language="AR"))
        s.add(_user("qa_notif_off@test.local", "client", "QA", "NotifOff",
                    language="EN", preferences={"notifications": {"signals": False}}))
        await s.flush()

        now = datetime.now(timezone.utc)
        s.add(Subscription(
            user_id=(await s.execute(select(User).where(User.email == CLIENT))).scalar_one().id,
            plan="professional", billing_cycle="monthly", price=59.0,
            start_date=now - timedelta(days=2), end_date=now + timedelta(days=28), active=True,
        ))
        await s.commit()
    _run_sql(_do)


def _login_token(c, email):
    r = c.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200 and r.json().get("access_token"), \
        f"{email} login failed: {r.text[:200]}"
    return r.json()["access_token"]


# ---------------------------------------------------------------------------
# 1. Pure pipeline checks (no DB, no HTTP)
# ---------------------------------------------------------------------------
def unit_checks() -> None:
    print("\n[1] Pipeline — preferences + rules + templates + channels")
    from api.services.notifications.preferences import get_user_notifications
    from api.services.notifications.rules import resolve_channels
    from api.services.notifications.templates import render_telegram

    class _U:
        preferences = {"notifications": {"signals": False, "tp": True}}

    prefs = get_user_notifications(_U)
    check(prefs["signals"] is False and prefs["tp"] is True and prefs["news"] is True,
          "preferences merge defaults + stored override", str(prefs))

    off = resolve_channels("SETUP_DETECTED", prefs)
    check(off == [], "SETUP_DETECTED gated off by signals toggle", str(off))
    on = resolve_channels("TP_HIT", prefs)
    check(on == ["telegram"], "TP_HIT routed to telegram", str(on))
    lic = resolve_channels("LICENSE_ACTIVATED", prefs)
    check(lic == ["email"], "LICENSE_ACTIVATED routed to email", str(lic))
    sys_ev = resolve_channels("SYSTEM_INFO", prefs)
    check(sys_ev == ["telegram"], "SYSTEM_INFO always to telegram", str(sys_ev))

    for lang in ("EN", "AR", "FR", "ES"):
        txt = render_telegram("TRADE_OPENED", {"symbol": "XAUUSD", "direction": "BUY", "price": 2410.5}, "", lang)
        check(bool(txt and "XAUUSD" in txt), f"render_telegram non-empty [{lang}]", txt[:60])
    fb = render_telegram("UNKNOWN_EVENT", {}, "raw fallback", "EN")
    check(fb == "raw fallback", "unknown event falls back to raw message", fb)

    # Channel mock delivery
    async def _channels():
        from api.services.notifications.channels import EmailChannel, TelegramChannel
        tg = await TelegramChannel().deliver(chat_id=1, text="x")
        skip = await TelegramChannel().deliver(chat_id=None, text="x")
        mail = await EmailChannel().deliver(to="a@b.c", subject="s", body="b")
        mail2 = await EmailChannel().deliver(to="", subject="s", body="b")
        return tg, skip, mail, mail2

    r_tg, r_skip, r_mail, r_mail2 = _run_async(_channels)
    check(r_tg.ok and r_tg.status == "delivered", "telegram channel mocked delivery",
          r_tg.detail)
    check(not r_skip.ok and r_skip.status == "skipped", "telegram channel skips no chat", r_skip.status)
    check(r_mail.ok and r_mail.status == "delivered", "email channel mocked delivery", r_mail.detail)
    check(not r_mail2.ok and r_mail2.status == "skipped", "email channel skips no recipient", r_mail2.status)


# ---------------------------------------------------------------------------
# 2. Dispatcher — dispatch + broadcast write audit delivery records
# ---------------------------------------------------------------------------
def dispatcher_checks() -> None:
    print("\n[2] Dispatcher — persisted delivery log (audit_logs)")
    async def _do(s):
        from sqlalchemy import select
        from database.models import User
        from api.services.notifications.dispatcher import NotificationDispatcher

        on_u = (await s.execute(select(User).where(User.email == "qa_notif_on@test.local"))).scalar_one()
        off_u = (await s.execute(select(User).where(User.email == "qa_notif_off@test.local"))).scalar_one()

        d = NotificationDispatcher()
        res_on = await d.dispatch(s, user=on_u, event_type="TRADE_OPENED",
                                  payload={"symbol": "XAUUSD", "direction": "BUY", "price": 2410.5})
        check("telegram" in res_on["channels"], "dispatch routes TRADE_OPENED for on-user",
              str(res_on["channels"]))
        check(any(r["status"] == "delivered" for r in res_on["results"]),
              "dispatch telegram delivered (mock)", str(res_on["results"]))
        check(bool(res_on["audit_id"]), "dispatch wrote audit delivery record",
              str(res_on.get("audit_id")))

        res_off = await d.dispatch(s, user=off_u, event_type="SETUP_DETECTED",
                                   payload={"symbol": "NAS100", "direction": "SELL"})
        check(res_off["channels"] == [], "dispatch skips telegram when signals off",
              str(res_off["channels"]))
        check(bool(res_off["audit_id"]), "dispatch audits even when nothing delivered",
              str(res_off.get("audit_id")))

        # broadcast to both users -> only the linked one is delivered
        all_users = (await s.execute(
            select(User).where(User.email.in_(["qa_notif_on@test.local", "qa_notif_off@test.local"]))
        )).scalars().all()
        bres = await d.broadcast(s, recipients=list(all_users), event_type="SYSTEM_INFO",
                                 message="Scheduled maintenance", lang="EN")
        check(bres["sent"] == 1 and bres["skipped"] == 1 and bres["failures"] == 0,
              "broadcast delivers to linked chat only", str(bres))
        check(bool(bres["audit_id"]), "broadcast wrote audit record", str(bres.get("audit_id")))

        await s.commit()
        from database.models import AuditLog
        cnt = (await s.execute(
            select(AuditLog).where(AuditLog.event_type == "notification.delivery")
        )).scalars().all()
        check(len(cnt) >= 3, f"notification.delivery records persisted ({len(cnt)} rows)",
              str(len(cnt)))
        return True
    check(_run_sql(_do), "dispatcher DB flow")


# ---------------------------------------------------------------------------
# 3. API access control + endpoints
# ---------------------------------------------------------------------------
def api_checks() -> None:
    print("\n[3] API — permission-gated delivery endpoints + system-health")
    from fastapi.testclient import TestClient
    from api.main import app

    new_paths = [
        "/api/admin/emails/status",
        "/api/admin/emails/test",
        "/api/admin/telegram/status",
        "/api/admin/telegram/test",
        "/api/admin/system-health/integrations",
    ]

    with TestClient(app) as c:
        # ---- unauth 401
        for p in new_paths:
            r = c.get(p) if not p.endswith("/test") else c.post(p, json={})
            check(r.status_code == 401, f"401 without token: {p}", f"got {r.status_code}")

        Hc = {"Authorization": "Bearer " + _login_token(c, CLIENT)}
        Ho = {"Authorization": "Bearer " + _login_token(c, OWNER)}
        Ha = {"Authorization": "Bearer " + _login_token(c, ADMIN)}

        # ---- client 403 everywhere
        for p in new_paths:
            r = c.get(p, headers=Hc) if not p.endswith("/test") else c.post(p, headers=Hc, json={})
            check(r.status_code == 403, f"client 403: {p}", f"got {r.status_code}")

        # ---- owner 200 + shape
        r = c.get("/api/admin/system-health/integrations", headers=Ho)
        check(r.status_code == 200, "owner system-health/integrations 200", r.text[:160])
        d = r.json()
        check(all(k in d for k in ("email", "telegram", "billing", "news", "engine")),
              "integrations registry shape", str(list(d.keys())))
        check("configured" in d["email"] and "status" in d["billing"],
              "integration entries carry status/configured", str(d["email"]))

        r = c.get("/api/admin/emails/status", headers=Ho)
        check(r.status_code == 200 and "recent_deliveries" in r.json(),
              "owner emails/status 200 + delivery log", r.text[:160])
        check(r.json().get("email_configured") is False and "smtp_host" not in r.json(),
              "emails/status never leaks secrets", str(r.json().get("email_configured")))

        r = c.get("/api/admin/telegram/status", headers=Ho)
        check(r.status_code == 200 and "linked_users" in r.json(),
              "owner telegram/status 200 + linked_users", r.text[:160])

        # ---- emails.send test (mock)
        r = c.post("/api/admin/emails/test", headers=Ho, json={"to": "owner@test.local"})
        check(r.status_code == 200 and r.json().get("success") and r.json().get("mock"),
              "owner emails/test mocked send", r.text[:160])

        # ---- telegram.send test (mock)
        r = c.post("/api/admin/telegram/test", headers=Ho, json={"chat_id": 100000001})
        check(r.status_code == 200 and r.json().get("success") and r.json().get("mock"),
              "owner telegram/test mocked send", r.text[:160])
        r = c.post("/api/admin/telegram/test", headers=Ho, json={"chat_id": "abc"})
        check(r.status_code == 400, "telegram/test rejects bad chat_id (400)", f"got {r.status_code}")

        # ---- admin (non-owner) also permitted
        r = c.post("/api/admin/emails/test", headers=Ha, json={})
        check(r.status_code == 200, "admin emails/test allowed (emails.send)", f"got {r.status_code}")

        # ---- audited
        r = c.get("/api/admin/audit-logs", headers=Ho, params={"action": "email.test"})
        j = r.json()
        check(any(i.get("action") == "email.test" for i in j.get("items", [])),
              "email.test audited", str(j.get("items", [])[:1]))
        r = c.get("/api/admin/audit-logs", headers=Ho, params={"action": "telegram.test"})
        j = r.json()
        check(any(i.get("action") == "telegram.test" for i in j.get("items", [])),
              "telegram.test audited", str(j.get("items", [])[:1]))

        # ---- honest restart status (no process manager)
        r = c.post("/api/admin/system-health/telegram/restart", headers=Ho)
        j = r.json()
        check(r.status_code == 200 and j.get("supported") is False,
              "telegram/restart honest unsupported", r.text[:160])
        r = c.post("/api/admin/system-health/mt5/restart", headers=Ho)
        check(r.status_code == 200 and r.json().get("supported") is False,
              "mt5/restart honest unsupported", r.text[:160])
        r = c.post("/api/admin/system-health/api/restart", headers=Ho)
        check(r.status_code == 200 and r.json().get("supported") is False,
              "api/restart honest unsupported", r.text[:160])

        # ---- engine control still works (regression)
        r = c.post("/api/admin/system-health/engine/restart", headers=Ho)
        check(r.status_code == 200 and r.json().get("success"),
              "engine restart still success (regression)", r.text[:160])


def main() -> int:
    print("=" * 62)
    print("Phase 6.0 Foundations QA — notifications + integrations")
    print("=" * 62)
    _seed()
    unit_checks()
    dispatcher_checks()
    api_checks()

    print("\n" + "=" * 62)
    print(f"TOTAL {PASSED + FAILED} | PASS {PASSED} | FAIL {FAILED}")
    for name, detail in ERRORS:
        print(f"  FAILED CHECK: {name} -> {detail}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())

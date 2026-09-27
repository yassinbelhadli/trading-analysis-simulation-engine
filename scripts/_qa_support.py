"""Support/Ticket system QA — shared records across ALL four surfaces.

Covers the implementation plan for the support/ticket phase:

API layer (client + admin + owner):
  - SP-001  unauthenticated guard on client + admin ticket surfaces
  - SP-002  client creates a ticket (TKT-* number, opening message, audit)
  - SP-003  client create validation (subject/description/category/priority)
  - SP-004  client scoping: own list only; foreign id -> 404; staff can read
  - SP-005  client reply appends to the shared conversation
  - SP-006  internal staff notes never leak to the client (list + detail)
  - SP-007  PATCH validation + resolved/closed timestamp semantics
  - SP-008  reopen clears resolved_at
  - SP-009  closed tickets block replies (client + staff) until reopened
  - SP-010  assign / unassign (tickets.assign) + support denied
  - SP-011  escalate writes full metadata + forces urgent
  - SP-012  ban suspends licenses + closes ticket; support denied
  - SP-013  metrics endpoint shape (owner portal)
  - SP-014  admin list filters (status / search / escalated)
  - SP-015  unified {success, audit_id, message} contract; audit rows REAL
  - SP-025  client payload strips staff-only keys

Telegram layer (shared records via the bot):
  - SP-016  /start -> support home entry exists
  - SP-017  full create flow writes source=telegram row with unique TKT-*
  - SP-018  list + detail render; HTML-injection description escaped
  - SP-019  internal note not leaked in Telegram detail
  - SP-020  Telegram reply flow appends a client message
  - SP-021  ownership: foreign ticket -> "not found"
  - SP-022  closed ticket blocks Telegram reply
  - SP-023  TICKET:STATUS filter works
  - SP-024  consecutive creations get DISTINCT ticket numbers

Run:  python scripts/_qa_support.py
Requires: QA DB (ict_funded_ea_qa) + TEST ENCRYPTION_KEY (see CLAUDE.md).
Idempotent: reseeds all fixture users every run.
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:cimoro2008@localhost:5432/ict_funded_ea_qa"
os.environ["ENCRYPTION_KEY"] = "XLX1vxl3BclZbOETIL-StfxdVDrWeRj5VBCG-eEQpr0="
os.environ["USE_MOCK_TELEGRAM_SCAN"] = "true"
os.environ["TELEGRAM_BOT_TOKEN"] = "777999:QA_TEST_TOKEN_FOR_SUPPORT"

PASSWORD = "SupportQA!789"
CLIENT = "qa_support_client@test.local"
ADMIN = "qa_support_admin@test.local"
SUPPORT = "qa_support_staff@test.local"
OWNER = "qa_support_owner@test.local"

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


async def _run_sql_async(fn):
    """_run_sql for use INSIDE the running event loop (avoids nested asyncio.run)."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    eng = create_async_engine(os.environ["DATABASE_URL"])
    factory = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as s:
            return await fn(s)
    finally:
        await eng.dispose()


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
        from database.repositories import LicenseRepository, UserRepository
        from security.access_control import seed_roles_and_permissions
        from security.password import hash_password

        await s.run_sync(lambda c: Base.metadata.create_all(c.bind))
        await seed_roles_and_permissions(s)

        # Wipe fixture users + their data first (messages cascade via FK).
        for acc in (await s.execute(select(TradingAccount))).scalars().all():
            await s.execute(delete(PaperTrade).where(PaperTrade.account_id == acc.id))
            await s.execute(delete(AccountScan).where(AccountScan.account_id == acc.id))
            await s.execute(delete(RiskProfile).where(RiskProfile.account_id == acc.id))
        await s.execute(delete(TicketMessage))
        await s.execute(delete(PaperTrade))
        await s.execute(delete(AccountScan))
        await s.execute(delete(RiskProfile))
        await s.execute(delete(TradingAccount))
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
            if r.name in {"admin", "support", "owner", "client"}
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

        s.add(_user(ADMIN, "admin", "QA", "Admin"))
        s.add(_user(SUPPORT, "support", "QA", "Support"))
        s.add(_user(OWNER, "owner", "QA", "Owner"))
        client_u = _user(CLIENT, "client", "QA", "Client")
        s.add(client_u)
        await s.flush()

        now = datetime.now(timezone.utc)
        s.add(Subscription(
            user_id=client_u.id, plan="professional", billing_cycle="monthly", price=59.0,
            start_date=now - timedelta(days=2), end_date=now + timedelta(days=28), active=True,
        ))
        s.add(License(
            user_id=client_u.id, license_key="QA-SUPPORT-LICENSE", plan="professional",
            status="active", max_accounts=3, expires_at=now + timedelta(days=28),
        ))
        await s.commit()

        # Telegram user (created the way the bot creates accounts).
        repo = UserRepository(s)
        tg = await repo.get_or_create_by_telegram(
            telegram_id=778001, telegram_username="qa_support_tg", first_name="Tina",
            language="EN",
        )
        # Second telegram user (Bob) so the foreign-ticket ownership test has a
        # real DB row to resolve (the bot's /start only shows the language
        # keyboard for brand-new users and does NOT create the row).
        await repo.get_or_create_by_telegram(
            telegram_id=778002, telegram_username="qa_support_tg2", first_name="Bob",
            language="EN",
        )
        lic_repo = LicenseRepository(s)
        lic = await lic_repo.get_by_key("QA-SUPPORT-TG-LICENSE")
        if not lic:
            lic = await lic_repo.create(
                user_id=tg.id, license_key="QA-SUPPORT-TG-LICENSE", plan="pro",
                max_accounts=2, expires_at=None,
            )
        lic.status = "active"
        lic.telegram_id = 778001
        lic.bound_at = None
        await s.commit()
    _run_sql(_do)


async def _req(c, method: str, url: str, **kw):
    """HTTP helper usable with httpx.AsyncClient from the single event loop."""
    return await getattr(c, method)(url, **kw)


async def _login(c, email, password=PASSWORD):
    return await _req(c, "post", "/auth/login", json={"email": email, "password": password})


async def _login_ok(c, email):
    r = await _login(c, email)
    assert r.status_code == 200 and r.json().get("access_token"), f"login {email} failed: {r.text[:200]}"
    return {"Authorization": "Bearer " + r.json()["access_token"]}


async def _audit_exists(audit_id: str):
    """Audit ids must be REAL rows — the unified contract forbids fake ids."""
    if not audit_id:
        return False

    async def _q(s):
        from sqlalchemy import select
        from database.models import AuditLog
        row = (await s.execute(select(AuditLog).where(AuditLog.id == audit_id))).scalar_one_or_none()
        return row is not None

    try:
        return bool(await _run_sql_async(_q))
    except Exception:
        return False


async def _license_status(user_id: str):
    async def _q(s):
        from sqlalchemy import select
        from database.models import License
        lic = (await s.execute(select(License).where(License.user_id == user_id))).scalars().all()
        return [l.status for l in lic]

    return await _run_sql_async(_q)


async def _count_messages(ticket_id: str) -> int:
    async def _q(s):
        from sqlalchemy import func, select
        from database.models import TicketMessage
        return (await s.execute(
            select(func.count(TicketMessage.id)).where(TicketMessage.ticket_id == ticket_id)
        )).scalar() or 0

    return await _run_sql_async(_q)


# ================================================================ API tests


async def _api_tests(c):
    print("\n[SP-001] Unauthenticated guard")
    for path in ["/api/client/support", "/api/admin/tickets", "/api/admin/tickets/metrics"]:
        r = await _req(c, "get", path)
        check(r.status_code == 401, f"401 without token: {path}", f"got {r.status_code}")

    print("\n[SP-002] Client creates a ticket")
    Hc = await _login_ok(c, CLIENT)
    r = await _req(c, "post", "/api/client/support", headers=Hc, json={
        "subject": "Cannot connect my MT5 account",
        "description": "My MT5 account fails to connect after the latest update. Please assist.",
        "category": "connection", "priority": "high",
    })
    d = r.json()
    check(r.status_code == 200 and d.get("ticket", {}).get("id"), "client create returns ticket",
          r.text[:160])
    tkt = d["ticket"]
    check(tkt.get("ticket_number", "").startswith("TKT-"), "server-assigned TKT-* number",
          tkt.get("ticket_number", ""))
    check(tkt.get("subject") == "Cannot connect my MT5 account", "subject echoed")
    check(tkt.get("source") == "dashboard", "source=dashboard")
    check(tkt.get("messages") and tkt["messages"][0].get("body") == d["ticket"]["description"],
          "opening TicketMessage duplicates description")
    check(tkt.get("status") == "open" and tkt.get("priority") == "high", "status/priority defaults")
    client_ticket_id = tkt["id"]
    client_ticket_number = tkt["ticket_number"]

    print("\n[SP-003] Client create validation")
    r = await _req(c, "post", "/api/client/support", headers=Hc, json={
        "subject": "ab", "description": "x" * 20, "category": "other",
    })
    check(r.status_code == 400, "subject < 3 rejected", f"got {r.status_code}")
    r = await _req(c, "post", "/api/client/support", headers=Hc, json={
        "subject": "valid subject here", "description": "short", "category": "other",
    })
    check(r.status_code == 400, "description < 10 rejected", f"got {r.status_code}")
    r = await _req(c, "post", "/api/client/support", headers=Hc, json={
        "subject": "valid subject here", "description": "x" * 20, "category": "nope",
    })
    check(r.status_code == 400, "invalid category rejected", f"got {r.status_code}")
    r = await _req(c, "post", "/api/client/support", headers=Hc, json={
        "subject": "valid subject here", "description": "x" * 20, "category": "other", "priority": "max",
    })
    check(r.status_code == 400, "invalid priority rejected", f"got {r.status_code}")

    print("\n[SP-004] Client scoping (ownership -> 404, staff can read)")
    r = await _req(c, "get", "/api/client/support", headers=Hc)
    d = r.json()
    check(r.status_code == 200 and isinstance(d.get("tickets"), list), "client list shape", r.text[:160])
    check(any(t["id"] == client_ticket_id for t in d["tickets"]), "own ticket in list")
    Ha = await _login_ok(c, ADMIN)
    r = await _req(c, "get", "/api/admin/tickets", headers=Ha)
    admin_list = r.json()
    check(r.status_code == 200 and any(t["id"] == client_ticket_id for t in admin_list.get("tickets", [])),
          "admin sees the same shared record", r.text[:160])
    r = await _req(c, "get", f"/api/admin/tickets/{client_ticket_id}", headers=Ha)
    check(r.status_code == 200 and r.json().get("ticket", {}).get("id") == client_ticket_id,
          "admin detail on client ticket (200)", r.text[:160])

    # Foreign id: the OTHER client (tg user has no API login) — use a random id.
    r = await _req(c, "get", f"/api/client/support/{uuid.uuid4()}", headers=Hc)
    check(r.status_code == 404, "foreign/unknown ticket id -> 404 (no enumeration)", f"got {r.status_code}")

    print("\n[SP-005] Client reply appends to shared conversation")
    r = await _req(c, "post", f"/api/client/support/{client_ticket_id}/reply", headers=Hc,
               json={"message": "I restarted MT5 and still get the same error."})
    check(r.status_code == 200 and r.json().get("message") == "Reply added", "client reply 200",
          r.text[:160])
    before = await _count_messages(client_ticket_id)
    check(before == 2, f"conversation has opening + reply ({before})", f"count={before}")

    print("\n[SP-006] Internal staff notes never leak to the client")
    r = await _req(c, "post", f"/api/admin/tickets/{client_ticket_id}/reply", headers=Ha,
               json={"message": "SECRET-INTERNAL-qa-marker", "is_internal": True})
    check(r.status_code == 200 and r.json().get("success") is True and r.json().get("message") == "Internal note added",
          "admin adds internal note", r.text[:160])
    r = await _req(c, "get", f"/api/client/support/{client_ticket_id}", headers=Hc)
    client_detail = r.json().get("ticket", {})
    all_client_text = str(client_detail)
    check("SECRET-INTERNAL-qa-marker" not in all_client_text,
          "client detail does not contain internal note")
    r = await _req(c, "get", f"/api/admin/tickets/{client_ticket_id}", headers=Ha)
    admin_detail = r.json().get("ticket", {})
    check("SECRET-INTERNAL-qa-marker" in str(admin_detail),
          "admin detail DOES contain the internal note")
    check(all(not m.get("is_internal") for m in client_detail.get("messages", [])),
          "client payload marks no message as internal")

    print("\n[SP-007] PATCH validation + resolved semantics")
    r = await _req(c, "patch", f"/api/admin/tickets/{client_ticket_id}", headers=Ha, json={"status": "exploded"})
    check(r.status_code == 400, "invalid status rejected", f"got {r.status_code}")
    r = await _req(c, "patch", f"/api/admin/tickets/{client_ticket_id}", headers=Ha, json={"status": "in_progress"})
    d = r.json()
    check(r.status_code == 200 and d.get("success") is True and d.get("audit_id"),
          "valid status update (unified contract)", r.text[:160])
    check(await _audit_exists(d.get("audit_id")), "PATCH audit row really exists")
    r = await _req(c, "patch", f"/api/admin/tickets/{client_ticket_id}", headers=Ha, json={"status": "resolved"})
    d = r.json()
    check(r.status_code == 200 and d.get("success"), "resolve", r.text[:160])
    r = await _req(c, "get", f"/api/admin/tickets/{client_ticket_id}", headers=Ha)
    check(r.json()["ticket"].get("resolved_at") is not None, "resolved_at set on resolve")

    print("\n[SP-008] Reopen clears resolved_at")
    r = await _req(c, "patch", f"/api/admin/tickets/{client_ticket_id}", headers=Ha, json={"status": "open"})
    check(r.status_code == 200 and r.json().get("success"), "reopen", r.text[:160])
    r = await _req(c, "get", f"/api/admin/tickets/{client_ticket_id}", headers=Ha)
    t = r.json()["ticket"]
    check(t.get("resolved_at") is None and t.get("closed_at") is None, "reopen clears timestamps")

    print("\n[SP-009] Closed tickets block replies until reopened")
    r = await _req(c, "patch", f"/api/admin/tickets/{client_ticket_id}", headers=Ha, json={"status": "closed"})
    check(r.status_code == 200 and r.json().get("success"), "close ticket", r.text[:160])
    r = await _req(c, "post", f"/api/client/support/{client_ticket_id}/reply", headers=Hc,
               json={"message": "can I still reply?"})
    check(r.status_code == 400, "client reply blocked on closed ticket", f"got {r.status_code}")
    r = await _req(c, "post", f"/api/admin/tickets/{client_ticket_id}/reply", headers=Ha,
               json={"message": "admin reply on closed"})
    check(r.status_code == 400, "admin reply blocked on closed ticket", f"got {r.status_code}")
    r = await _req(c, "patch", f"/api/admin/tickets/{client_ticket_id}", headers=Ha, json={"status": "open"})
    check(r.status_code == 200, "reopen after close", r.text[:160])
    r = await _req(c, "post", f"/api/admin/tickets/{client_ticket_id}/reply", headers=Ha,
               json={"message": "works again after reopen"})
    check(r.status_code == 200, "reply works after reopen", f"got {r.status_code}")

    print("\n[SP-010] Assign / unassign (tickets.assign)")
    Hs = await _login_ok(c, SUPPORT)
    users = (await _req(c, "get", "/api/admin/users?role=admin", headers=Ha)).json().get("items", [])
    admin_user_id = users[0]["id"] if users else None
    check(bool(admin_user_id), "admin staff user resolvable")
    r = await _req(c, "post", f"/api/admin/tickets/{client_ticket_id}/assign", headers=Ha,
               json={"assignee_id": admin_user_id})
    d = r.json()
    check(r.status_code == 200 and d.get("success") and d.get("assignee", {}).get("id") == admin_user_id,
          "assign sets assignee", r.text[:160])
    r = await _req(c, "get", f"/api/admin/tickets/{client_ticket_id}", headers=Ha)
    check(r.json()["ticket"].get("assignee_id") == admin_user_id, "assignee_id persisted")
    check(r.json()["ticket"].get("assigned_at") is not None, "assigned_at set")
    r = await _req(c, "post", f"/api/admin/tickets/{client_ticket_id}/assign", headers=Ha, json={"assignee_id": "none"})
    check(r.status_code == 200 and r.json().get("success"), "unassign via none", r.text[:160])
    r = await _req(c, "get", f"/api/admin/tickets/{client_ticket_id}", headers=Ha)
    check(r.json()["ticket"].get("assignee_id") is None, "assignee cleared")
    r = await _req(c, "post", f"/api/admin/tickets/{client_ticket_id}/assign", headers=Hs,
               json={"assignee_id": admin_user_id})
    check(r.status_code == 403, "support cannot assign (403)", f"got {r.status_code}")

    print("\n[SP-011] Escalate writes full metadata + forces urgent")
    r = await _req(c, "post", f"/api/admin/tickets/{client_ticket_id}/escalate", headers=Hs,
               json={"target": "owner", "reason": "Client account drained by bug"})
    d = r.json()
    check(r.status_code == 200 and d.get("success") is True and d.get("audit_id"),
          "escalate (support holds tickets.update)", r.text[:160])
    r = await _req(c, "get", f"/api/admin/tickets/{client_ticket_id}", headers=Ha)
    t = r.json()["ticket"]
    check(t.get("escalated") is True, "escalated=True")
    check(t.get("escalation_target") == "owner", f"escalation_target={t.get('escalation_target')}")
    check(t.get("escalation_reason") == "Client account drained by bug", "escalation_reason persisted")
    check(t.get("escalated_by") is not None, "escalated_by recorded (legacy bug fixed)")
    check(t.get("escalated_at") is not None, "escalated_at recorded")
    check(t.get("priority") == "urgent", "escalation forces priority=urgent")
    r = await _req(c, "post", f"/api/admin/tickets/{client_ticket_id}/escalate", headers=Hc)
    check(r.status_code == 403, "client cannot escalate (403)", f"got {r.status_code}")

    print("\n[SP-013] Metrics endpoint (owner portal)")
    Ho = await _login_ok(c, OWNER)
    r = await _req(c, "get", "/api/admin/tickets/metrics", headers=Ho)
    d = r.json()
    check(r.status_code == 200 and d.get("success") is True, "metrics 200", r.text[:160])
    m = d.get("metrics", {})
    check(all(k in m for k in ("total", "open", "in_progress", "resolved", "closed", "escalated", "urgent")),
          "metrics keys present", str(list(m)))
    check(m.get("total", 0) >= 1, f"metrics.total >= 1 ({m.get('total')})")

    print("\n[SP-014] Admin list filters")
    r = await _req(c, "get", "/api/admin/tickets?status=open", headers=Ha)
    d = r.json()
    check(r.status_code == 200 and d["tickets"] and all(t["status"] == "open" for t in d["tickets"]),
          "status filter applied", r.text[:160])
    r = await _req(c, "get", "/api/admin/tickets?search=Cannot+connect", headers=Ha)
    d = r.json()
    check(r.status_code == 200 and any("Cannot connect" in t["subject"] for t in d["tickets"]),
          "search filter by subject", r.text[:160])
    r = await _req(c, "get", "/api/admin/tickets?escalated=true", headers=Ha)
    d = r.json()
    check(r.status_code == 200 and d["tickets"] and all(t["escalated"] for t in d["tickets"]),
          "escalated filter", r.text[:160])
    r = await _req(c, "get", "/api/admin/tickets?status=nope", headers=Ha)
    check(r.status_code == 400, "invalid status filter rejected", f"got {r.status_code}")

    print("\n[SP-015] Unified mutation contract everywhere")
    mutations = [
        ("reply", await _req(c, "post", f"/api/admin/tickets/{client_ticket_id}/reply", headers=Ha,
                         json={"message": "contract check reply"})),
        ("patch", await _req(c, "patch", f"/api/admin/tickets/{client_ticket_id}", headers=Ha, json={"priority": "low"})),
        ("assign", await _req(c, "post", f"/api/admin/tickets/{client_ticket_id}/assign", headers=Ha,
                          json={"assignee_id": admin_user_id})),
        ("escalate", await _req(c, "post", f"/api/admin/tickets/{client_ticket_id}/escalate", headers=Ha,
                            json={"target": "owner"})),
    ]
    for name, r in mutations:
        d = r.json()
        check(r.status_code == 200 and d.get("success") is True and d.get("audit_id") and d.get("message"),
              f"{name} returns {{success, audit_id, message}}", r.text[:160])
        if r.status_code == 200 and d.get("audit_id"):
            check(await _audit_exists(d["audit_id"]), f"{name} audit_id is a REAL row")

    print("\n[SP-025] Client payload strips staff-only keys")
    r = await _req(c, "get", f"/api/client/support/{client_ticket_id}", headers=Hc)
    t = r.json().get("ticket", {})
    stripped = all(k not in t for k in ("assignee_id", "escalation_target", "escalated_by",
                                        "replied_by", "closed_by", "license", "assignee"))
    check(stripped, "no staff-only keys in client payload", str(sorted(t.keys())))

    print("\n[SP-012] Ban suspends licenses + closes ticket; support denied")
    r = await _req(c, "post", f"/api/admin/tickets/{client_ticket_id}/ban", headers=Hs)
    check(r.status_code == 403, "support cannot ban (403)", f"got {r.status_code}")
    r = await _req(c, "post", f"/api/admin/tickets/{client_ticket_id}/ban", headers=Ha)
    d = r.json()
    check(r.status_code == 200 and d.get("success") is True and d.get("audit_id"),
          "admin ban succeeds (frozen contract)", r.text[:160])
    check(await _audit_exists(d.get("audit_id")), "ban audit row really exists")
    r = await _req(c, "get", f"/api/admin/tickets/{client_ticket_id}", headers=Ha)
    check(r.json()["ticket"].get("status") == "closed", "ticket closed after ban")
    check("banned" in (r.json()["ticket"].get("admin_reply") or "").lower(), "ban marker appended")
    lic_statuses = await _license_status(r.json()["ticket"]["user_id"])
    check(all(st == "suspended" for st in lic_statuses), f"licenses suspended ({lic_statuses})",
          str(lic_statuses))

    return client_ticket_id


# ================================================================ Telegram tests


async def _telegram_tests(client_ticket_id: str):
    from _qa_wizard import Chat, FakeUser  # fakes from the wizard harness
    from database.db import async_session_factory
    from database.models import SupportTicket
    from database.repositories import UserRepository
    from sqlalchemy import select

    A = Chat(FakeUser(778001, "qa_support_tg", "Tina"))
    B = Chat(FakeUser(778002, "qa_support_tg2", "Bob"))

    print("\n[SP-016] /start -> support home entry")
    await A.send("/start")
    cbs = A.callbacks()
    check(any("MENU:SUPPORT" in cb or "TICKET:LIST" in cb for cb in cbs),
          "support entry present in main menu", str(cbs[:10]))

    print("\n[SP-017] Telegram create flow -> shared record (source=telegram)")
    # Support home is reached via MENU:SUPPORT (used by keyboards).
    await A.click("MENU:SUPPORT")
    check(A.current_text and "Support" in A.current_text or "ticket" in A.current_text.lower(),
          "support home rendered")
    check(A.has_callback("TICKET:CREATE") and A.has_callback("TICKET:LIST"),
          "support home has create + my tickets", str(A.callbacks()[:6]))
    await A.click("TICKET:CREATE")
    check(A.has_callback("TICKET:CAT:"), "category picker rendered", str(A.callbacks()[:8]))
    await A.click("TICKET:CAT:connection")
    check("waiting_for" in A.context.user_data and A.context.user_data["waiting_for"] == "TICKET_DESCRIPTION",
          "waiting state TICKET_DESCRIPTION set")
    desc = "<b>my mt5</b> broker connection <script>alert(1)</script> failing since update"
    await A.send(desc)
    check(A.current_text and "Ticket Created" in A.current_text, "creation confirmation shown",
          A.current_text[:200])

    async with async_session_factory() as s:
        user = await UserRepository(s).get_by_telegram_id(778001)
        rows = (await s.execute(
            select(SupportTicket).where(SupportTicket.user_id == user.id)
        )).scalars().all()
    check(len(rows) == 1, f"exactly one shared ticket row ({len(rows)})", str(len(rows)))
    tg_ticket = rows[0]
    check(tg_ticket.source == "telegram", f"source=telegram ({tg_ticket.source})")
    check(tg_ticket.ticket_number.startswith("TKT-"), "TKT-* number", tg_ticket.ticket_number)
    check(tg_ticket.subject == "connection", "subject mirrors category")
    check(tg_ticket.ticket_number != client_ticket_id and tg_ticket.id != client_ticket_id,
          "distinct record from dashboard ticket")
    tg_ticket_id = tg_ticket.id
    tg_ticket_number = tg_ticket.ticket_number

    print("\n[SP-018] List + detail render; HTML injection escaped")
    await A.click("TICKET:LIST")
    check(tg_ticket_number in A.current_text, "list shows the ticket", A.current_text[:200])
    await A.click(f"TICKET:VIEW:{tg_ticket_id}")
    check("<b>my mt5</b>" not in A.current_text, "raw <b> tag escaped out of detail")
    check("&lt;b&gt;" in A.current_text or "&lt;script&gt;" in A.current_text,
          "description HTML-escaped in render")

    print("\n[SP-019] Internal note not leaked in Telegram detail")
    await A.click("TICKET:LIST")
    await A.click(f"TICKET:VIEW:{tg_ticket_id}")
    # Re-open detail so the view reflects the current conversation.
    note = "TG-INTERNAL-qa-marker-7711"
    async with async_session_factory() as s:
        from api.services.ticket_service import add_message
        from database.models import User as U
        admin_row = (await s.execute(select(U).where(U.email == ADMIN))).scalar_one()
        # Reload the ticket in THIS session — services expect an attached
        # instance (exactly how the API routes call them).
        tg_ticket = (await s.execute(
            select(SupportTicket).where(SupportTicket.id == tg_ticket_id)
        )).scalar_one()
        await add_message(
            s, tg_ticket, body=note, author_user_id=admin_row.id,
            author_role="admin", author_name="QA Admin", is_internal=True,
        )
    await A.click("TICKET:LIST")
    await A.click(f"TICKET:VIEW:{tg_ticket_id}")
    check(note not in A.current_text, "internal note absent from Telegram detail")

    print("\n[SP-020] Telegram reply flow appends a client message")
    await A.click(f"TICKET:REPLY:{tg_ticket_id}")
    check(A.context.user_data.get("waiting_for") == "TICKET_REPLY", "reply waiting state set")
    await A.send("Please help me fix this connection issue asap.")
    check(A.current_text and "Reply Added" in A.current_text, "reply confirmation", A.current_text[:160])
    check(await _count_messages(tg_ticket_id) == 3, "tg conversation = opening + note + reply")

    print("\n[SP-021] Ownership: foreign ticket -> not found")
    await B.send("/start")
    await B.click("TICKET:LIST")
    check(B.current_text and "no tickets" in B.current_text.lower(), "user B has empty list",
          B.current_text[:160])
    await B.click(f"TICKET:VIEW:{tg_ticket_id}")
    check("not found" in B.current_text.lower(), "foreign ticket -> Ticket not found",
          B.current_text[:160])

    print("\n[SP-022] Closed ticket blocks Telegram reply")
    async with async_session_factory() as s:
        from api.services.ticket_service import update_ticket_fields
        from database.models import User as U2
        admin_row = (await s.execute(select(U2).where(U2.email == ADMIN))).scalar_one()
        tg_ticket = (await s.execute(
            select(SupportTicket).where(SupportTicket.id == tg_ticket_id)
        )).scalar_one()
        await update_ticket_fields(
            s, tg_ticket, fields={"status": "closed"}, actor=admin_row, actor_role="admin"
        )
    await A.click(f"TICKET:REPLY:{tg_ticket_id}")
    check("closed" in A.current_text.lower(), "closed ticket blocks reply", A.current_text[:200])
    check(A.context.user_data.get("waiting_for") != "TICKET_REPLY", "no waiting state on closed")

    print("\n[SP-023] TICKET:STATUS filter")
    await A.click("TICKET:STATUS:closed")
    check(tg_ticket_number in A.current_text, "closed filter shows the closed ticket",
          A.current_text[:200])

    print("\n[SP-024] Distinct numbering across surfaces")
    async with async_session_factory() as s:
        rows = (await s.execute(select(SupportTicket).order_by(SupportTicket.created_at))).scalars().all()
    nums = [r.ticket_number for r in rows]
    check(len(nums) == len(set(nums)), f"all ticket numbers unique ({nums})", str(nums))
    check(all(n.startswith("TKT-") for n in nums), "all numbers TKT-*", str(nums))

    return tg_ticket_number


def main() -> int:
    _seed()

    async def _run_all():
        import httpx

        from api.main import app

        # Single event loop for the whole suite: the app's async engine must
        # bind to ONE loop, so API tests use ASGITransport (not TestClient).
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            client_ticket_id = await _api_tests(c)
            await _telegram_tests(client_ticket_id)

    asyncio.run(_run_all())

    print(f"\nTOTAL {PASSED + FAILED} | PASS {PASSED} | FAIL {FAILED} | ERROR {len(ERRORS)}")
    for name, detail in ERRORS:
        print(f"  FAILED: {name} :: {detail}")
    return 1 if (FAILED or ERRORS) else 0


if __name__ == "__main__":
    sys.exit(main())

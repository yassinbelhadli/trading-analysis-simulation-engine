"""QA for Sprint 2 (Client Integrations): MT5 Accounts, Telegram, Download EA, Settings.

Scenarios:
  MT5: add / delete / duplicate / invalid login / wrong password / wrong server /
       disconnect / reconnect / rename / plan limits / no-license guard
  Telegram: connect / change chat / disconnect / preferences / invalid keys /
            test notification (unconfigured + test-mode)
  Download: info / check-updates (outdated + up-to-date) / download (valid) /
            invalid license / expired license / missing file
  Settings: save / reload / theme / language / symbols / invalid values

Idempotent: reseeds all test users + EA builds + artifact file every run.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:cimoro2008@localhost:5432/ict_funded_ea_qa"
os.environ["ENCRYPTION_KEY"] = "XLX1vxl3BclZbOETIL-StfxdVDrWeRj5VBCG-eEQpr0="
os.environ["USE_MOCK_TELEGRAM_SCAN"] = "true"
os.environ.pop("TELEGRAM_BOT_TOKEN", None)
os.environ.pop("TELEGRAM_TEST_MODE", None)

PASSWORD = "Passw0rd!123"
EA_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "storage", "ea", "ict_ea_v1.2.0.ex5")

RESULTS: list[tuple[bool, str]] = []


def check(cond: bool, label: str):
    RESULTS.append((bool(cond), label))
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}")


async def _seed(s):
    from datetime import datetime, timedelta, timezone
    from pathlib import Path
    from sqlalchemy import delete, select
    from database.base import Base
    from database.models import (
        AccountScan, AuditLog, EABuild, License, LoginSession, PaperTrade,
        RiskProfile, Role, Subscription, TradingAccount, User,
    )
    from security.access_control import seed_roles_and_permissions
    from security.audit import log_event
    from security.password import hash_password

    await s.run_sync(lambda c: Base.metadata.create_all(c.bind))
    await seed_roles_and_permissions(s)
    role = (await s.execute(select(Role).where(Role.name == "client"))).scalar_one_or_none()
    now = datetime.now(timezone.utc)

    # EA builds (idempotent upsert) --------------------------------------------
    ea_dir = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "storage" / "ea"
    ea_dir.mkdir(parents=True, exist_ok=True)
    (ea_dir / "ict_ea_v1.2.0.ex5").write_bytes(b"ICT-FUNDED-EA-PLACEHOLDER")

    async def _upsert_build(version, notes, changelog, windows_file, is_latest):
        existing = (await s.execute(select(EABuild).where(EABuild.version == version))).scalar_one_or_none()
        if not existing:
            s.add(EABuild(version=version, release_notes=notes, changelog=changelog,
                          windows_file=windows_file, macos_file=None,
                          is_latest=is_latest, released_at=now - timedelta(days=1)))
    await _upsert_build("1.0.0", "Initial release", "- Initial release", None, False)
    await _upsert_build("1.2.0", "Added news filter + session control",
                        "- Added news filter\n- Session kill-zone tuning",
                        "ict_ea_v1.2.0.ex5", True)
    # enforce single latest
    latest = (await s.execute(select(EABuild))).scalars().all()
    for b in latest:
        b.is_latest = (b.version == "1.2.0")
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
                 first_name=first, last_name="Sprint2",
                 role_id=role.id if role else None,
                 account_status="active", email_verified=True, language="EN")
        s.add(u)
        await s.flush()
        return u

    # main user: active pro license (3 accounts)
    await reset("sprint2@testmail.com")
    u = await new_user("sprint2@testmail.com", "Main")
    lic = License(user_id=u.id, license_key="QA-SPRINT2-ACTIVE", plan="professional",
                  status="active", max_accounts=3, expires_at=now + timedelta(days=30))
    s.add(lic)
    await log_event(s, "license.activated", "License activated", user_id=u.id)

    # limit user: starter license (1 account)
    await reset("sprint2-limit@testmail.com")
    u = await new_user("sprint2-limit@testmail.com", "Limit")
    s.add(License(user_id=u.id, license_key="QA-SPRINT2-LIMIT", plan="starter",
                  status="active", max_accounts=1, expires_at=now + timedelta(days=30)))

    # no-license user
    await reset("sprint2-invalid@testmail.com")
    await new_user("sprint2-invalid@testmail.com", "NoLic")

    # expired-license user
    await reset("sprint2-expired@testmail.com")
    u = await new_user("sprint2-expired@testmail.com", "Expired")
    s.add(License(user_id=u.id, license_key="QA-SPRINT2-EXP", plan="standard",
                  status="expired", max_accounts=1, expires_at=now - timedelta(days=1)))

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


def _patch_connector():
    """Simulate credential failures for specific inputs; otherwise mock-success."""
    from telegram_bot.services.mt_connector import MTAccountScanResult, mt_connector

    def _fail(login_data, state, message):
        return MTAccountScanResult(
            success=False, state=state, message=message,
            platform=login_data.platform, server=login_data.server, login=login_data.login,
            broker_name=None, account_balance=0.0, account_equity=0.0,
            account_currency="USD", detected_symbols=[], supported_markets=[],
        )

    async def _fake_test(login_data):
        if "badserver" in (login_data.server or ""):
            return _fail(login_data, "CONNECTION_FAILED", "Wrong server")
        if login_data.password == "wrongpass":
            return _fail(login_data, "CONNECTION_FAILED", "Wrong password")
        if login_data.login == "000000":
            return _fail(login_data, "CONNECTION_FAILED", "Invalid login")
        return mt_connector._mock_result(login_data)

    mt_connector.test_connection = _fake_test


def _simulate_bind(code: str, tg_id: int) -> str:
    """Simulate the Telegram user sending `/bind <CODE>` to the bot.

    Runs the real bind_command handler with stub update/context objects and a
    main-thread session factory (the app's shared factory is bound to the
    TestClient event loop). Returns the bot's reply text.
    """
    import telegram_bot.commands.bind_cmd as bind_cmd
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    eng = create_async_engine(os.environ["DATABASE_URL"])
    _orig = bind_cmd.async_session_factory
    bind_cmd.async_session_factory = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)

    class FakeMessage:
        def __init__(self):
            self.replies = []

        async def reply_text(self, text, **kwargs):
            self.replies.append(text)

    class FakeUpdate:
        def __init__(self, msg):
            self.effective_user = type("U", (), {"id": tg_id, "username": f"qa_tg_{tg_id}"})()
            self.message = msg

    class FakeContext:
        def __init__(self):
            self.args = [code]
            self.user_data = {}

    async def go():
        try:
            msg = FakeMessage()
            await bind_cmd.bind_command(FakeUpdate(msg), FakeContext())
            return "\n".join(msg.replies)
        finally:
            bind_cmd.async_session_factory = _orig
            await eng.dispose()

    return asyncio.run(go())


def main():
    _run_seed()

    from fastapi.testclient import TestClient
    from api.main import app
    _patch_connector()
    # The app loads config/.env which contains a real bot token; neutralise it so
    # the "not configured" path is deterministic (no real network calls in QA).
    os.environ["TELEGRAM_BOT_TOKEN"] = ""

    with TestClient(app) as c:
        H = _login(c, "sprint2@testmail.com")
        H_limit = _login(c, "sprint2-limit@testmail.com")
        H_invalid = _login(c, "sprint2-invalid@testmail.com")
        H_expired = _login(c, "sprint2-expired@testmail.com")

        # ---- MT5 Accounts --------------------------------------------------------
        print("\n[1] MT5 Accounts")
        r = c.get("/api/client/accounts", headers=H)
        check(r.status_code == 200 and r.json()["items"] == [], "list starts empty")
        lim = r.json()["limits"]
        check(lim == {"used": 0, "max": 3, "unlimited": False}, f"limits 0/3 (got {lim})")

        add_body = {"platform": "MT5", "server": "ICMarkets-Live08", "login": "123456",
                    "password": "secret", "name": "FTMO Demo"}
        r = c.post("/api/client/accounts", headers=H, json=add_body)
        check(r.status_code == 200, f"add account 200 (got {r.status_code} {r.text[:120]})")
        acc = r.json()["account"]
        check(acc["connected"] is True and acc["engine_status"] == "ACTIVE", "account connected after add")
        check(acc["balance"] == 10000.0 and acc["broker"] == "Mock Broker", "snapshot from scan stored")
        check(acc["license_id"], "license bound")

        r = c.get("/api/client/accounts", headers=H)
        check(len(r.json()["items"]) == 1 and r.json()["limits"]["used"] == 1, "used=1 after add")

        r = c.post("/api/client/accounts", headers=H, json=add_body)
        check(r.status_code == 409, f"duplicate -> 409 (got {r.status_code})")

        r = c.post("/api/client/accounts", headers=H, json={**add_body, "login": "000000"})
        check(r.status_code == 400 and "Invalid login" in r.text, "invalid login -> 400")
        r = c.post("/api/client/accounts", headers=H, json={**add_body, "login": "123457", "password": "wrongpass"})
        check(r.status_code == 400 and "Wrong password" in r.text, "wrong password -> 400")
        r = c.post("/api/client/accounts", headers=H, json={**add_body, "server": "badserver"})
        check(r.status_code == 400 and "Wrong server" in r.text, "wrong server -> 400")
        r = c.post("/api/client/accounts", headers=H, json={"platform": "MT5"})
        check(r.status_code == 400, "missing fields -> 400")
        r = c.post("/api/client/accounts", headers=H, json={**add_body, "platform": "MT6"})
        check(r.status_code == 400, "unsupported platform -> 400")

        aid = acc["id"]
        r = c.patch(f"/api/client/accounts/{aid}", headers=H, json={"name": "FTMO Demo 2"})
        check(r.status_code == 200 and r.json()["account"]["name"] == "FTMO Demo 2", "rename works")

        r = c.post(f"/api/client/accounts/{aid}/reconnect", headers=H, json={})
        check(r.status_code == 200 and r.json()["account"]["connected"] is True, "reconnect -> connected")
        r = c.post(f"/api/client/accounts/{aid}/disconnect", headers=H)
        check(r.status_code == 200 and r.json()["account"]["connected"] is False, "disconnect -> disconnected")
        r = c.post(f"/api/client/accounts/{aid}/reconnect", headers=H, json={})
        check(r.status_code == 200 and r.json()["account"]["connected"] is True, "reconnect again -> connected")

        r = c.delete(f"/api/client/accounts/{aid}", headers=H)
        check(r.status_code == 200, "delete account -> 200")
        r = c.get("/api/client/accounts", headers=H)
        check(r.json()["items"] == [] and r.json()["limits"]["used"] == 0, "empty after delete")
        r = c.delete(f"/api/client/accounts/{aid}", headers=H)
        check(r.status_code == 404, "delete missing -> 404")

        # plan limit user
        r = c.post("/api/client/accounts", headers=H_limit,
                   json={"platform": "MT5", "server": "FTMO-Live", "login": "111111", "password": "secret"})
        check(r.status_code == 200, "limit user add 1st account")
        r = c.post("/api/client/accounts", headers=H_limit,
                   json={"platform": "MT5", "server": "FTMO-Live", "login": "222222", "password": "secret"})
        check(r.status_code == 400 and "Max accounts (1)" in r.text, f"limit user 2nd account rejected (got {r.status_code})")

        # no-license user
        r = c.post("/api/client/accounts", headers=H_invalid,
                   json={"platform": "MT5", "server": "ICMarkets-Live08", "login": "333333", "password": "secret"})
        check(r.status_code == 400 and "No active license" in r.text, "add without license -> 400")

        # ---- Telegram -------------------------------------------------------------
        print("\n[2] Telegram")
        r = c.get("/api/client/telegram", headers=H)
        j = r.json()
        check(j["connected"] is False and j["chat_id"] is None, "telegram disconnected initially")
        check(j["notifications"]["signals"] is True and j["notifications"]["monthly_report"] is True,
              "notification defaults true")

        # Secure bind flow: the dashboard issues a short-lived code; the bot links
        # the real Telegram id. A client-supplied chat_id is never accepted.
        r = c.post("/api/client/telegram/connect", headers=H, json={"chat_id": 111})
        j = r.json()
        check(r.status_code == 200 and len(j.get("code", "")) == 8
              and j.get("expires_in_seconds") == 600 and "/bind" in j.get("message", ""),
              "connect issues 8-char bind code (chat_id ignored)")
        code1 = j["code"]
        r = c.post("/api/client/telegram/connect", headers=H, json={"chat_id": 222})
        check(r.status_code == 200 and r.json().get("code") not in (None, code1),
              "second connect rotates the code")
        code2 = r.json()["code"]
        r = c.get("/api/client/telegram", headers=H)
        check(r.json()["connected"] is False and r.json()["chat_id"] is None,
              "still unconnected until the bot binds the code")

        # Wrong code -> rejected by the bot, status stays unconnected
        reply = _simulate_bind("WRONG000", 777777)
        check("invalid or expired" in reply.lower(), "wrong bind code rejected by bot")
        r = c.get("/api/client/telegram", headers=H)
        check(r.json()["connected"] is False, "still unconnected after wrong code")

        # Real bind with the current code -> linked to the Telegram id
        reply = _simulate_bind(code2, 777777)
        check("telegram connected" in reply.lower(), "valid bind code accepted by bot")
        r = c.get("/api/client/telegram", headers=H)
        check(r.json()["connected"] is True and r.json()["chat_id"] == 777777,
              "status reflects bound Telegram id")

        # Rotate again + rebind to a different Telegram account
        r = c.post("/api/client/telegram/connect", headers=H)
        j = r.json()
        check(r.status_code == 200 and j.get("code") not in (None, code2),
              "third connect issues fresh code")
        _simulate_bind(j["code"], 888888)
        r = c.get("/api/client/telegram", headers=H)
        check(r.json()["connected"] is True and r.json()["chat_id"] == 888888,
              "rebind moves connection to new Telegram id")

        r = c.patch("/api/client/telegram/preferences", headers=H,
                    json={"notifications": {"signals": False, "news": False}, "language": "ar"})
        check(r.status_code == 200 and r.json()["notifications"]["signals"] is False
              and r.json()["language"] == "AR", "preferences saved + language AR")
        r = c.get("/api/client/telegram", headers=H)
        check(r.json()["notifications"]["signals"] is False and r.json()["language"] == "AR",
              "preferences persisted")
        r = c.patch("/api/client/telegram/preferences", headers=H, json={"notifications": {"bogus": True}})
        check(r.status_code == 400, "invalid notification key -> 400")
        r = c.patch("/api/client/telegram/preferences", headers=H, json={"language": "XX"})
        check(r.status_code == 400, "invalid language -> 400")
        r = c.post("/api/client/telegram/test", headers=H)
        check(r.status_code == 400 and "not configured" in r.text, "test notification unconfigured -> 400")
        os.environ["TELEGRAM_TEST_MODE"] = "true"
        r = c.post("/api/client/telegram/test", headers=H)
        check(r.status_code == 200 and r.json()["chat_id"] == 888888, "test notification (test mode) -> 200")
        os.environ.pop("TELEGRAM_TEST_MODE", None)
        r = c.post("/api/client/telegram/disconnect", headers=H)
        check(r.status_code == 200 and r.json()["connected"] is False, "disconnect -> 200")
        r = c.post("/api/client/telegram/test", headers=H)
        check(r.status_code == 400, "test while disconnected -> 400")

        # ---- Download EA ----------------------------------------------------------
        print("\n[3] Download EA")
        r = c.get("/api/client/ea", headers=H)
        j = r.json()
        check(r.status_code == 200 and j["latest"]["version"] == "1.2.0", "latest version 1.2.0")
        check(len(j["changelog"]) == 2 and j["latest"]["windows_available"] is True, "changelog + windows available")
        r = c.post("/api/client/ea/check-updates", headers=H, json={"current_version": "1.0.0"})
        check(r.json()["update_available"] is True and r.json()["latest_version"] == "1.2.0",
              "check-updates: outdated -> available")
        r = c.post("/api/client/ea/check-updates", headers=H, json={"current_version": "1.2.0"})
        check(r.json()["update_available"] is False, "check-updates: up-to-date")
        r = c.post("/api/client/ea/check-updates", headers=H, json={"current_version": "2.0.0"})
        check(r.json()["update_available"] is False, "check-updates: ahead -> not available")
        r = c.get("/api/client/ea/download/latest", headers=H)
        check(r.status_code == 200 and r.content == b"ICT-FUNDED-EA-PLACEHOLDER", "download latest 200 + content")
        r = c.get("/api/client/ea/download/1.2.0", headers=H)
        check(r.status_code == 200, "download by version string -> 200")
        r = c.get("/api/client/ea/download/nope", headers=H)
        check(r.status_code == 404, "unknown build -> 404")
        r = c.get("/api/client/ea/download/1.0.0", headers=H)
        check(r.status_code == 404, "build without file -> 404")
        r = c.get("/api/client/ea/download/latest", headers=H_invalid)
        check(r.status_code == 403, "invalid license (none) -> 403")
        r = c.get("/api/client/ea/download/latest", headers=H_expired)
        check(r.status_code == 403, "expired license -> 403")

        # ---- Settings --------------------------------------------------------------
        print("\n[4] Settings")
        r = c.get("/api/client/settings", headers=H)
        p = r.json()["preferences"]
        check(p["theme"] == "system" and p["default_symbols"] == ["XAUUSD", "NAS100", "BTCUSD"],
              "settings defaults")
        r = c.patch("/api/client/settings", headers=H, json={"preferences": {
            "theme": "dark", "default_symbols": ["XAUUSD"],
            "news_filter": {"enabled": False, "block_before_min": 15},
        }})
        check(r.status_code == 200, "patch settings -> 200")
        r = c.get("/api/client/settings", headers=H)
        p = r.json()["preferences"]
        check(p["theme"] == "dark" and p["default_symbols"] == ["XAUUSD"]
              and p["news_filter"]["enabled"] is False and p["news_filter"]["block_before_min"] == 15,
              "settings reload reflects changes")
        r = c.patch("/api/client/settings", headers=H, json={"preferences": {"theme": "blue"}})
        check(r.status_code == 400, "invalid theme -> 400")
        r = c.patch("/api/client/settings", headers=H, json={"preferences": {"default_timeframes": ["M2"]}})
        check(r.status_code == 400, "invalid timeframe -> 400")
        r = c.patch("/api/client/settings", headers=H, json={"preferences": {"trading_sessions": ["PARIS"]}})
        check(r.status_code == 400, "invalid session -> 400")
        r = c.patch("/api/client/settings", headers=H, json={"preferences": {"risk": {"mode": "insane"}}})
        check(r.status_code == 400, "invalid risk mode -> 400")
        r = c.patch("/api/client/settings", headers=H, json={"preferences": {"risk": {"max_risk_per_trade": 99}}})
        check(r.status_code == 400, "risk out of range -> 400")
        r = c.patch("/api/client/settings", headers=H, json={"preferences": {"notifications": {"bogus": True}}})
        check(r.status_code == 400, "invalid notification key -> 400")
        r = c.patch("/api/client/settings", headers=H, json={"language": "XX"})
        check(r.status_code == 400, "invalid language -> 400")
        r = c.patch("/api/client/settings", headers=H, json={"first_name": "Main2", "preferences": {"theme": "light"}})
        check(r.status_code == 200 and r.json()["preferences"]["theme"] == "light", "scalar + prefs together")
        r = c.get("/api/client/settings", headers=H)
        check(r.json()["first_name"] == "Main2" and r.json()["preferences"]["theme"] == "light",
              "reload after combined save")

        # ---- Auth guard ------------------------------------------------------------
        print("\n[5] Auth guard")
        r = c.get("/api/client/accounts")
        check(r.status_code == 401, "unauthenticated accounts -> 401")
        r = c.get("/api/client/telegram")
        check(r.status_code == 401, "unauthenticated telegram -> 401")
        r = c.get("/api/client/ea")
        check(r.status_code == 401, "unauthenticated ea -> 401")

    passed = sum(1 for ok, _ in RESULTS if ok)
    total = len(RESULTS)
    print(f"\n=== Sprint 2 QA: {passed}/{total} PASS ===")
    if passed != total:
        print("Failed checks:")
        for ok, label in RESULTS:
            if not ok:
                print(f"  - {label}")
        sys.exit(1)


if __name__ == "__main__":
    main()

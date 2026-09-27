"""QA harness for the Telegram onboarding wizard + account management + alerts.

Spawns its OWN PostgreSQL database (ict_funded_ea_qa) so it never touches
production data. Drives the real handlers (start / callback / message) with
fake Telegram update objects, mock MT connection mode (USE_MOCK_TELEGRAM_SCAN=1)
and a fake engine manager.

Every test records PASS / FAIL / ERROR with a duration. Failing tests that
surface REAL bugs are reported as FAIL with the bug in the reason field.

Run:
    python scripts/_qa_wizard.py

Requires a local PostgreSQL server and the same credentials as config.
"""
from __future__ import annotations

import asyncio
import inspect
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

# ---------------------------------------------------------------- env
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "777999:QA_TEST_TOKEN_FOR_WIZARD")
os.environ.setdefault("JWT_SECRET", "qa-jwt-secret-0000000000000000")
os.environ.setdefault("ENCRYPTION_KEY", "XLX1vxl3BclZbOETIL-StfxdVDrWeRj5VBCG-eEQpr0=")
os.environ["DATABASE_URL"] = (
    "postgresql+asyncpg://postgres:cimoro2008@localhost:5432/ict_funded_ea_qa"
)
os.environ["USE_MOCK_TELEGRAM_SCAN"] = "true"
os.environ["DEMO_ONLY"] = "true"
os.environ["ALLOW_REAL_TRADING"] = "false"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------- imports
import telegram  # noqa: E402

from database.db import async_session_factory, init_db, close_db, engine  # noqa: E402
from database.models import (  # noqa: E402
    User,
    License,
    TradingAccount,
    RiskProfile,
    SupportTicket,
)
from database.repositories import (  # noqa: E402
    UserRepository,
    LicenseRepository,
    AccountRepository,
)
from telegram_bot.handlers.start import start_handler  # noqa: E402
from telegram_bot.handlers.callback_handler import callback_handler, _route_callback  # noqa: E402
from telegram_bot.handlers.message_handler import message_handler  # noqa: E402
from telegram_bot.ui.callbacks import Callback  # noqa: E402

# ================================================================ fakes


class FakeUser:
    def __init__(self, uid, username="", first_name="", last_name=""):
        self.id = uid
        self.username = username
        self.first_name = first_name
        self.last_name = last_name
        self.language_code = "en"


class FakeChat:
    def __init__(self, chat_id):
        self.id = chat_id
        self.deleted = []

    async def delete_message(self, message_id):
        self.deleted.append(message_id)


class FakeMessage:
    _counter = 0

    def __init__(self, chat, text=None, reply_markup=None, message_id=None,
                 session=None):
        FakeMessage._counter += 1
        self.message_id = message_id if message_id is not None else FakeMessage._counter
        self.chat = chat
        self.text = text
        self.reply_markup = reply_markup
        self.photo_sent = []
        self.session = session

    async def reply_text(self, text=None, parse_mode=None, reply_markup=None, **kw):
        m = FakeMessage(self.chat, text=text, reply_markup=reply_markup,
                        session=self.session)
        if self.session is not None:
            self.session.last_message = m
        return m

    async def reply_photo(self, photo=None, caption=None, parse_mode=None,
                          reply_markup=None, **kw):
        self.photo_sent.append({"photo": photo, "caption": caption})
        return self

    async def edit_message_text(self, text=None, parse_mode=None,
                                reply_markup=None, **kw):
        self.text = text
        self.reply_markup = reply_markup
        return True


class FakeCallbackQuery:
    def __init__(self, bot, message, data, from_user):
        self.bot = bot
        self.message = message
        self.data = data
        self.from_user = from_user
        self.answers = []

    async def answer(self, text=None, show_alert=False):
        self.answers.append({"text": text, "show_alert": show_alert})

    async def edit_message_text(self, text=None, parse_mode=None,
                                reply_markup=None, **kw):
        self.message.text = text
        self.message.reply_markup = reply_markup
        return True


class FakeUpdate:
    def __init__(self, message=None, callback_query=None, user=None, bot=None):
        self.message = message
        self.callback_query = callback_query
        self._user = user or (callback_query.from_user if callback_query else None)
        self.bot = bot

    @property
    def effective_user(self):
        return self._user

    @property
    def effective_message(self):
        if self.message is not None:
            return self.message
        if self.callback_query is not None:
            return self.callback_query.message
        return None


class FakeBot:
    """Bot used by AlertService / SignalService / etc."""

    def __init__(self):
        self.messages = []

    async def send_message(self, chat_id, text, parse_mode=None, reply_markup=None, **kw):
        self.messages.append({
            "type": "text", "chat_id": chat_id, "text": text,
            "parse_mode": parse_mode, "reply_markup": reply_markup,
        })

    async def send_photo(self, chat_id, photo, caption=None, parse_mode=None,
                         reply_markup=None, **kw):
        self.messages.append({
            "type": "photo", "chat_id": chat_id, "photo": photo, "caption": caption,
            "parse_mode": parse_mode, "reply_markup": reply_markup,
        })


class FakeContext:
    def __init__(self):
        self.user_data = {}
        self.bot_data = {}
        self.args = []
        self.bot = FakeBot()


class FakeRenderer:
    """Zero-cost stand-in for RenderService so QA does not touch matplotlib."""

    def render_snapshot(self, snapshot, minimal=True):
        return b"PNGDATA-SNAPSHOT"

    def render_setup(self, candidate, minimal=True):
        return b"PNGDATA-SETUP"

    def render_trade(self, result, candles=None, plan=None, symbol="", minimal=True):
        return b"PNGDATA-TRADE"

    def to_bytes(self, image):
        return image if isinstance(image, bytes) else b"PNGDATA-BYTES"


class Chat:
    """Per-user Telegram session: one user_data context, one chat id."""

    def __init__(self, user: FakeUser):
        self.user = user
        self.context = FakeContext()
        self.chat = FakeChat(user.id)
        self.bot = FakeBot()
        self.last_query = None
        self.last_message = None
        self.last_error = None
        self._last_action = None

    async def send(self, text):
        msg = FakeMessage(self.chat, text=text, session=self)
        self._last_action = "send"
        self.last_query = None
        self.last_message = None
        upd = FakeUpdate(message=msg, user=self.user)
        try:
            if text.strip().startswith("/"):
                await start_handler(upd, self.context)
            else:
                await message_handler(upd, self.context)
        except Exception as e:  # surface real crashes
            self.last_error = e
            raise
        if self.last_message is None:
            self.last_message = msg
        return self.last_message

    async def click(self, data):
        msg = FakeMessage(self.chat, session=self)
        self._last_action = "click"
        self.last_message = None
        q = FakeCallbackQuery(self.bot, msg, data, self.user)
        upd = FakeUpdate(callback_query=q, user=self.user)
        try:
            await callback_handler(upd, self.context)
        except Exception as e:
            self.last_error = e
            raise
        self.last_query = q
        if self.last_message is None:
            self.last_message = msg
        return q

    @property
    def current_text(self):
        if self._last_action == "click":
            if self.last_query is not None and self.last_query.message.text:
                return self.last_query.message.text
            if self.last_message is not None and self.last_message.text:
                return self.last_message.text
            return ""
        if self.last_message is not None and self.last_message.text:
            return self.last_message.text
        return ""

    @property
    def current_keyboard(self):
        if self._last_action == "click":
            if self.last_query is not None and self.last_query.message.reply_markup is not None:
                return self.last_query.message.reply_markup
            if self.last_message is not None:
                return self.last_message.reply_markup
            return None
        if self.last_message is not None:
            return self.last_message.reply_markup
        return None

    def callbacks(self):
        kb = self.current_keyboard
        if kb is None or not getattr(kb, "inline_keyboard", None):
            return []
        out = []
        for row in kb.inline_keyboard:
            for btn in row:
                if getattr(btn, "callback_data", None):
                    out.append(btn.callback_data)
        return out

    def find_callback(self, prefix):
        for cb in self.callbacks():
            if cb.startswith(prefix):
                return cb
        return None

    def has_callback(self, prefix):
        return self.find_callback(prefix) is not None


# ================================================================ engine fake

FAKE_ENGINE = {"running": set(), "calls": []}


async def _fe_start(account_id):
    FAKE_ENGINE["running"].add(account_id)
    FAKE_ENGINE["calls"].append(("start", account_id))


async def _fe_pause(account_id):
    FAKE_ENGINE["running"].discard(account_id)
    FAKE_ENGINE["calls"].append(("pause", account_id))


async def _fe_resume(account_id):
    FAKE_ENGINE["running"].add(account_id)
    FAKE_ENGINE["calls"].append(("resume", account_id))


async def _fe_restart(account_id):
    FAKE_ENGINE["running"].add(account_id)
    FAKE_ENGINE["calls"].append(("restart", account_id))


async def _fe_stop(account_id):
    FAKE_ENGINE["running"].discard(account_id)
    FAKE_ENGINE["calls"].append(("stop", account_id))


def _fe_is_running(account_id):
    return account_id in FAKE_ENGINE["running"]


def patch_engine_manager():
    from core_engine import engine_manager as em
    eng = em.engine_manager
    eng.start = _fe_start
    eng.pause = _fe_pause
    eng.resume = _fe_resume
    eng.restart = _fe_restart
    eng.stop = _fe_stop
    eng.is_running = _fe_is_running


# ================================================================ QA runner


class QA:
    def __init__(self):
        self.results = []

    async def run(self, test_id, name, func, allow_error=False):
        t0 = time.perf_counter()
        try:
            result = func()
            if inspect.isawaitable(result):
                result = await result
            if result is None:
                ok, detail = True, ""
            elif isinstance(result, tuple) and len(result) == 2:
                ok, detail = result
            else:
                ok, detail = bool(result), ""
            status = "PASS" if ok else "FAIL"
        except Exception as e:
            status = "ERROR" if not allow_error else "FAIL"
            ok, detail = False, f"{type(e).__name__}: {e}"
        ms = (time.perf_counter() - t0) * 1000
        self.results.append({
            "id": test_id, "name": name, "status": status,
            "detail": detail, "ms": round(ms, 1),
        })

    def report(self):
        total = len(self.results)
        passed = sum(1 for r in self.results if r["status"] == "PASS")
        failed = sum(1 for r in self.results if r["status"] == "FAIL")
        errors = sum(1 for r in self.results if r["status"] == "ERROR")
        total_ms = sum(r["ms"] for r in self.results)
        lines = [
            "=" * 78,
            "QA WIZARD REGRESSION REPORT",
            "=" * 78,
        ]
        for r in self.results:
            mark = {"PASS": "PASS", "FAIL": "FAIL", "ERROR": "ERROR"}[r["status"]]
            lines.append(f"[{mark}] {r['id']} {r['name']}")
            if r["status"] != "PASS" and r["detail"]:
                for ln in str(r["detail"]).splitlines()[:6]:
                    lines.append(f"      -> {ln}")
            lines.append(f"      ({r['ms']} ms)")
        lines.append("-" * 78)
        lines.append(
            f"TOTAL {total} | PASS {passed} | FAIL {failed} | ERROR {errors} | "
            f"{total_ms:.0f} ms"
        )
        print("\n".join(lines))
        return passed, failed, errors


QA_CTX = QA()


async def qa(test_id, name, func, allow_error=False):
    await QA_CTX.run(test_id, name, func, allow_error=allow_error)


# ================================================================ db helpers


async def get_user(telegram_id):
    async with async_session_factory() as s:
        repo = UserRepository(s)
        return await repo.get_by_telegram_id(telegram_id)


async def get_account(account_id):
    async with async_session_factory() as s:
        return await AccountRepository(s).get_by_id(account_id)


async def seed():
    now = time.time()
    users = {
        777001: ("alice", "Alice", "QA-PERS-AAAA", 2),
        777002: ("bob", "Bob", "QA-FUND-BBBB", 1),
        777004: ("dana", "Dana", "QA-FUND-DDDD", 2),
    }
    async with async_session_factory() as s:
        user_repo = UserRepository(s)
        lic_repo = LicenseRepository(s)
        for tid, (uname, fname, key, max_acc) in users.items():
            user = await user_repo.get_or_create_by_telegram(
                telegram_id=tid, telegram_username=uname, first_name=fname,
                language="EN",
            )
            lic = await lic_repo.get_by_key(key)
            if not lic:
                lic = await lic_repo.create(
                    user_id=user.id, license_key=key, plan="pro",
                    max_accounts=max_acc, expires_at=None,
                )
            lic.status = "active"
            lic.telegram_id = tid
            lic.bound_at = None
        await s.commit()
    return now


async def reset_db():
    """Truncate QA tables so every run starts from a clean, deterministic state."""
    from sqlalchemy import text

    async with engine.begin() as conn:
        await conn.execute(text(
            "TRUNCATE TABLE users, licenses, trading_accounts "
            "RESTART IDENTITY CASCADE"
        ))


# ================================================================ static audits


def audit_command_registration():
    # Registration moved to the shared factory in app.py; bot.py just boots it.
    app_src = (ROOT / "telegram_bot" / "app.py").read_text(encoding="utf-8")
    bot_src = (ROOT / "telegram_bot" / "bot.py").read_text(encoding="utf-8")
    registered = set(re.findall(r'CommandHandler\(\s*"([a-z_]+)"', app_src))
    registered |= set(re.findall(r'CommandHandler\(\s*"([a-z_]+)"', bot_src))
    cmd_dir = ROOT / "telegram_bot" / "commands"
    expected = set()
    if cmd_dir.is_dir():
        for f in cmd_dir.glob("*.py"):
            if f.name == "__init__.py":
                continue
            m = re.match(r"([a-z_]+)\.py", f.name)
            if m:
                expected.add(m.group(1))
    missing = sorted(expected - registered)
    return not missing, (
        "Bug: telegram commands never registered: " + ", ".join(missing)
        if missing else "ok"
    )


def audit_callback_coverage():
    from telegram_bot.ui.callbacks import Callback as CB

    src = (ROOT / "telegram_bot" / "handlers" / "callback_handler.py").read_text(
        encoding="utf-8"
    )
    prefixes = set(re.findall(r'startswith\(\s*"([^"}{]+)"', src))
    handled = set(prefixes)
    handled |= set(re.findall(r'callback == "([^"]+)"', src))
    for m in re.finditer(r'callback == Callback\.([A-Z_]+)', src):
        val = getattr(CB, m.group(1), None)
        if val:
            handled.add(val)
    for m in re.finditer(r'callback in \[([^\]]+)\]', src):
        for token in m.group(1).split(","):
            token = token.strip()
            if token.startswith("Callback."):
                val = getattr(CB, token.split(".", 1)[1], None)
                if val:
                    handled.add(val)
            elif token.startswith('"'):
                handled.add(token.strip('"'))

    kb_dir = ROOT / "telegram_bot" / "ui" / "keyboards"
    produced = []
    for f in kb_dir.glob("*.py"):
        src2 = f.read_text(encoding="utf-8")
        for m in re.finditer(r'callback_data\s*=\s*"([^"}{]+)"', src2):
            produced.append(m.group(1))
        for m in re.finditer(r'callback_data\s*=\s*Callback\.([A-Z_]+)', src2):
            val = getattr(CB, m.group(1), None)
            if val:
                produced.append(val)

    uncovered = []
    for cb in produced:
        if cb in handled:
            continue
        if any(cb.startswith(p) for p in prefixes):
            continue
        uncovered.append(cb)
    uncovered = sorted(set(uncovered))
    return not uncovered, (
        "Keyboard callbacks with no router branch: " + ", ".join(uncovered)
        if uncovered else "all keyboard callbacks routed"
    )


def audit_route_literals():
    """Ensure known account/menu prefixes have explicit router branches."""
    src = (ROOT / "telegram_bot" / "handlers" / "callback_handler.py").read_text(
        encoding="utf-8"
    )
    startswith = set(re.findall(r'startswith\(\s*"([^"}{]+)"', src))
    required = [
        "ACCOUNT:OPEN:", "ACCOUNT:PAUSE:", "ACCOUNT:RESUME:", "ACCOUNT:RESTART:",
        "ACCOUNT:RESCAN:", "ACCOUNT:RENAME:", "ACCOUNT:REMOVE:", "SETTINGS:",
        "RMS:", "RMC:", "RMX:", "BROKER:", "MODE:", "PROP:", "FUNDED_SIZE:",
        "CHALLENGE:", "BACK_", "PLATFORM:", "PROP_PROGRAM:", "SERVER:",
        "TICKET:CAT:", "ANALYSIS:",
    ]
    missing = [p for p in required if p not in startswith]
    return not missing, (
        "Missing router prefixes: " + ", ".join(missing) if missing else "ok"
    )


# ================================================================ journeys


async def journey_personal(chat: Chat):
    """User A: personal account via ic_markets, with validation negatives."""
    # /start (existing user, license, no accounts)
    await chat.send("/start")
    assert "Main Menu" in chat.current_text, chat.current_text
    await chat.click(Callback.MENU_ACCOUNTS)
    assert chat.has_callback("ADD_ACCOUNT"), "accounts page"
    await chat.click(Callback.ADD_ACCOUNT)
    assert chat.has_callback(Callback.PERSONAL), "account type page"
    await chat.click(Callback.PERSONAL)
    assert chat.has_callback("BROKER:"), "broker page"
    await chat.click("BROKER:ic_markets")
    assert chat.has_callback("MODE:"), "mode page"
    await chat.click("MODE:balanced")
    assert chat.context.user_data.get("waiting_for") == "ACCOUNT_BALANCE"
    # invalid balance
    await chat.send("5")
    assert "between $20 and $5000" in chat.current_text, chat.current_text
    await chat.send("1000")
    assert "Balance saved" in chat.current_text, chat.current_text
    assert chat.has_callback("MT5_CONTINUE"), "mt5 warning page"
    await chat.click("MT5_CONTINUE")
    assert chat.has_callback("TERMS_ACCEPT"), "terms page"
    await chat.click("TERMS_ACCEPT")
    # ic_markets supports MT4+MT5 -> platform chooser appears
    assert chat.has_callback("PLATFORM:MT5"), "platform page: " + chat.current_text
    await chat.click("PLATFORM:MT5")
    assert chat.has_callback("SERVER:"), "servers page"
    server_cb = chat.find_callback("SERVER:")
    assert server_cb and server_cb != "SERVER:OTHER"
    await chat.click(server_cb)
    assert chat.context.user_data.get("waiting_for") == "MT_LOGIN"
    await chat.send("123")
    assert "numbers only" in chat.current_text.lower(), chat.current_text
    await chat.send("12345678")
    assert chat.context.user_data.get("waiting_for") == "MT_PASSWORD"
    await chat.send("qa-password-1")
    assert chat.has_callback("CONFIRM_SETUP"), "confirm after scan: " + chat.current_text
    await chat.click(Callback.CONFIRM_SETUP)
    assert chat.has_callback(Callback.ACTIVATE_BOT), "activation page: " + chat.current_text
    await chat.click(Callback.ACTIVATE_BOT)
    assert "Bot Activated" in chat.current_text, chat.current_text


async def journey_funded(chat: Chat):
    """User D: funded account via FTMO 2-Step Swing + activation + management."""
    await chat.send("/start")
    assert "Main Menu" in chat.current_text, chat.current_text
    await chat.click(Callback.ADD_ACCOUNT)
    await chat.click(Callback.FUNDED)
    assert chat.has_callback("PROP:"), "prop firms page"
    await chat.click("PROP:ftmo")
    assert chat.has_callback("PROP_PROGRAM:"), "programs page"
    await chat.click("PROP_PROGRAM:ftmo_2_step_swing")
    assert "2-Step Swing" in chat.current_text, chat.current_text
    assert chat.has_callback("FUNDED_SIZE:"), "sizes page"
    await chat.click("FUNDED_SIZE:100K")
    assert chat.has_callback("MODE:"), "mode page"
    await chat.click("MODE:balanced")
    assert chat.has_callback("MT5_CONTINUE"), "ftmo -> mt5 warning"
    await chat.click("MT5_CONTINUE")
    assert chat.has_callback("TERMS_ACCEPT"), "terms page"
    await chat.click("TERMS_ACCEPT")
    # FTMO supports MT4+MT5 -> platform chooser appears
    assert chat.has_callback("PLATFORM:MT5"), "ftmo platform page: " + chat.current_text
    await chat.click("PLATFORM:MT5")
    assert chat.has_callback("SERVER:"), "ftmo servers page: " + chat.current_text
    server_cb = chat.find_callback("SERVER:")
    assert server_cb and server_cb != "SERVER:OTHER"
    await chat.click(server_cb)
    assert chat.context.user_data.get("waiting_for") == "MT_LOGIN"
    await chat.send("12345678")
    assert chat.context.user_data.get("waiting_for") == "MT_PASSWORD"
    await chat.send("qa-password-2")
    assert chat.has_callback("CONFIRM_SETUP"), "confirm after scan: " + chat.current_text
    await chat.click(Callback.CONFIRM_SETUP)
    assert chat.has_callback(Callback.ACTIVATE_BOT), chat.current_text
    await chat.click(Callback.ACTIVATE_BOT)
    assert "Bot Activated" in chat.current_text, chat.current_text


async def journey_c_negatives(chat: Chat):
    """User C: first-run + license negative paths."""
    await chat.send("/start")
    assert chat.has_callback(Callback.LANG_EN), "language keyboard"
    await chat.click(Callback.LANG_EN)
    assert "No Active License" in chat.current_text, chat.current_text
    assert chat.has_callback(Callback.ENTER_LICENSE_KEY), "no-license keyboard"
    await chat.click(Callback.ENTER_LICENSE_KEY)
    assert chat.context.user_data.get("waiting_for") == "LICENSE_KEY"
    await chat.send("QA-INVALID-XX")
    assert "Invalid license key" in chat.current_text, chat.current_text
    await chat.send("QA-PERS-AAAA")  # A's license, bound to A's telegram
    assert "bound to another" in chat.current_text.lower(), chat.current_text


async def journey_b_language(chat: Chat):
    """User B: start with license (no accounts) + language switch AR <-> EN."""
    await chat.send("/start")
    assert "Main Menu" in chat.current_text, chat.current_text
    assert chat.has_callback(Callback.MENU_ACCOUNTS), "main menu"
    await chat.click(Callback.MENU_LANGUAGE)
    assert chat.has_callback(Callback.LANG_AR), "language menu"
    await chat.click(Callback.LANG_AR)
    assert chat.context.user_data.get("language") == "AR"
    assert "القائمة الرئيسية" in chat.current_text, "arabic main menu: " + chat.current_text
    b = await get_user(777002)
    assert b.language == "AR", f"DB language expected AR, got {b.language}"
    # switch back
    await chat.click(Callback.MENU_LANGUAGE)
    await chat.click(Callback.LANG_EN)
    assert "Main Menu" in chat.current_text, chat.current_text
    b = await get_user(777002)
    assert b.language == "EN"


async def journey_d_management(chat: Chat, account_id: str):
    await chat.click(Callback.MENU_MAIN)
    assert chat.has_callback(Callback.MENU_ACCOUNTS), "main menu"
    await chat.click(Callback.MENU_ACCOUNTS)
    assert chat.has_callback(f"ACCOUNT:OPEN:{account_id}"), "accounts list"
    await chat.click(f"ACCOUNT:OPEN:{account_id}")
    assert "Account" in chat.current_text, "detail page: " + chat.current_text
    assert chat.has_callback(f"ACCOUNT:PAUSE:{account_id}"), "detail keyboard"
    assert chat.has_callback(f"SETTINGS:{account_id}"), "settings button"

    # rename
    await chat.click(f"ACCOUNT:RENAME:{account_id}")
    assert chat.context.user_data.get("waiting_for") == "ACCOUNT_RENAME"
    await chat.send("Dana Swing")
    assert "Dana Swing" in chat.current_text, chat.current_text
    acc = await get_account(account_id)
    assert acc.name == "Dana Swing"

    # risk settings -> aggressive
    await chat.click(Callback.MENU_MAIN)
    await chat.click(Callback.MENU_ACCOUNTS)
    await chat.click(f"ACCOUNT:OPEN:{account_id}")
    await chat.click(f"SETTINGS:{account_id}")
    assert chat.has_callback(f"RMS:{account_id}:"), "risk mode keyboard"
    await chat.click(f"RMS:{account_id}:a")
    assert chat.has_callback(f"RMC:{account_id}:a"), "risk confirm keyboard"
    await chat.click(f"RMC:{account_id}:a")
    assert "Risk mode changed" in chat.current_text, chat.current_text
    acc = await get_account(account_id)
    assert acc.risk_profile.mode == "aggressive", f"got {acc.risk_profile.mode}"
    assert abs(acc.risk_profile.max_risk_trade - 1.0) < 1e-6

    # pause / resume
    await chat.click(f"ACCOUNT:PAUSE:{account_id}")
    acc = await get_account(account_id)
    assert acc.engine_status == "PAUSED"
    await chat.click(f"ACCOUNT:RESUME:{account_id}")
    acc = await get_account(account_id)
    assert acc.engine_status == "ACTIVE"

    # rescan (mock) -> balance snapshot 10000
    await chat.click(f"ACCOUNT:RESCAN:{account_id}")
    assert "Balance" in chat.current_text and "OK" in chat.current_text, chat.current_text
    acc = await get_account(account_id)
    assert abs((acc.balance_snapshot or 0) - 10000) < 1e-6, acc.balance_snapshot

    # menu pages
    await chat.click(Callback.MENU_MAIN)
    await chat.click(Callback.MENU_STATUS)
    assert "System Status" in chat.current_text, chat.current_text
    await chat.click(Callback.NAV_BACK)
    await chat.click(Callback.MENU_MAIN)
    await chat.click(Callback.MENU_PERFORMANCE)
    assert "Performance Dashboard" in chat.current_text, chat.current_text
    await chat.click(Callback.NAV_BACK)
    await chat.click(Callback.MENU_MAIN)
    await chat.click(Callback.MENU_LICENSE)
    assert "License Info" in chat.current_text, chat.current_text
    assert "QA-FUND-DDDD" in chat.current_text, chat.current_text

    # support page + ticket flow (bug expected)
    await chat.click(Callback.NAV_BACK)
    await chat.click(Callback.MENU_MAIN)
    await chat.click(Callback.MENU_SUPPORT)
    assert "Support" in chat.current_text, chat.current_text
    assert chat.has_callback("TICKET:CREATE"), "support keyboard"
    await chat.click("TICKET:CREATE")
    assert chat.has_callback("TICKET:CAT:"), "category keyboard"
    await chat.click("TICKET:CAT:billing")
    assert chat.context.user_data.get("waiting_for") == "TICKET_DESCRIPTION"
    await chat.send("My billing invoice is not showing my latest payment.")
    # NOTE: reaching here means ticket creation succeeded -> bug fixed

    # remove account
    await chat.click(Callback.MENU_MAIN)
    await chat.click(Callback.MENU_ACCOUNTS)
    await chat.click(f"ACCOUNT:OPEN:{account_id}")
    await chat.click(f"ACCOUNT:REMOVE:{account_id}")
    assert chat.has_callback(f"ACCOUNT:REMOVE_CONFIRM:{account_id}"), "confirm keyboard"
    await chat.click(f"ACCOUNT:REMOVE_CONFIRM:{account_id}")
    assert "Account Removed" in chat.current_text, chat.current_text
    acc = await get_account(account_id)
    assert acc.removed_at is not None
    assert acc.engine_status == "REMOVED"
    assert acc.license_id is None


# ================================================================ alerts audit


async def alert_audit():
    from telegram_bot.services.alert_service import AlertService

    bot = FakeBot()
    svc = AlertService(bot, renderer=FakeRenderer())
    d_user = await get_user(777004)
    user_id = d_user.id

    def data_for(etype, **extra):
        return {"user_id": user_id, "event_type": etype, "data": extra, "message": ""}

    from core_engine.events.event_types import EventType

    SNAPSHOT = {
        "structure": {"bos_detected": True, "mss_detected": True},
        "liquidity": {"sweep_detected": True},
        "fvg": [{"top": 1.0, "bottom": 0.9}],
        "drawing": {"buy_sell": "BUY", "entry_price": 1.0, "sl_price": 0.95,
                    "tp": [1.05]},
        "scoring": {"score": 82, "confidence_score": 74},
    }
    SIGNAL = {"symbol": "XAUUSD", "direction": "BUY", "score": 82,
              "confidence": 74, "entry_price": 1.0, "stop_loss": 0.95,
              "take_profit": 1.05, "risk_reward": 2.5, "lot_size": 0.1,
              "timeframe": "M5", "session": "London", "snapshot": SNAPSHOT}

    cases = []
    svc._last_sent.clear()

    async def capture(name, etype, payload, msg=""):
        svc._last_sent.clear()
        before = len(bot.messages)
        await svc._dispatch(data_for(etype, **(payload or {}), **_evt_extra(etype, msg)))
        return len(bot.messages) > before

    def _evt_extra(etype, msg):
        return {"message": msg}

    cases.append(("setup_detected", EventType.SETUP_DETECTED.value, SIGNAL))
    cases.append(("paper_planned", EventType.PAPER_TRADE_PLANNED.value, dict(SIGNAL)))
    cases.append(("trade_opened", EventType.TRADE_OPENED.value,
                  {"ticket": "123", "symbol": "XAUUSD", "side": "BUY",
                   "filled_price": 1.002, "lot_size": 0.1, "snapshot": SNAPSHOT}))
    cases.append(("trade_closed", EventType.TRADE_CLOSED.value,
                  {"symbol": "XAUUSD", "realized_pnl": 120.0, "realized_r": 2.5,
                   "exit_reason": "TP_HIT"}))
    cases.append(("tp_hit", EventType.TP_HIT.value,
                  {"symbol": "XAUUSD", "price": 1.05, "realized_pnl": 120.0}))
    cases.append(("sl_hit", EventType.SL_HIT.value,
                  {"symbol": "XAUUSD", "price": 0.95, "realized_pnl": -80.0}))
    cases.append(("be_moved", EventType.BREAK_EVEN_MOVED.value,
                  {"symbol": "XAUUSD", "breakeven_price": 1.0}))
    cases.append(("trailing", EventType.TRAILING_STOP_UPDATED.value,
                  {"symbol": "XAUUSD"}))
    cases.append(("partial_close", EventType.PARTIAL_CLOSE.value,
                  {"symbol": "XAUUSD", "realized_pnl": 40.0, "remaining_pct": "50%"}))
    cases.append(("trade_blocked", EventType.TRADE_BLOCKED.value,
                  {"symbol": "XAUUSD", "direction": "SELL", "warnings": ["News filter"]},
                  "High impact news"))
    cases.append(("news_updated", EventType.NEWS_UPDATED.value,
                  {"event": "NFP", "impact": "HIGH", "currency": "USD",
                   "time": "14:30"}))
    cases.append(("news_countdown", EventType.NEWS_COUNTDOWN.value,
                  {"event": "NFP", "minutes_remaining": 30}))
    cases.append(("error_event", EventType.ERROR.value, None, "Engine tick failed"))
    cases.append(("health_warning", EventType.HEALTH_WARNING.value, None, "Latency high"))
    cases.append(("system_info", EventType.SYSTEM_INFO.value, None, "Backup done"))

    ok_all = True
    details = []
    for name, etype, payload, *rest in cases:
        msg = rest[0] if rest else ""
        sent = await capture(name, etype, payload, msg)
        if not sent:
            ok_all = False
            details.append(f"{name}: no message delivered")
    return ok_all, "; ".join(details) if details else "all alert types delivered"


async def alert_no_snapshot_bug():
    """Snapshot-less signal should still send a text-only signal, but hits the
    `reasons` NameError (alert_service._send_signal)."""
    from telegram_bot.services.alert_service import AlertService
    from core_engine.events.event_types import EventType

    bot = FakeBot()
    svc = AlertService(bot, renderer=FakeRenderer())
    d_user = await get_user(777004)
    svc._last_sent.clear()
    payload = {"symbol": "NAS100", "direction": "SELL", "score": 70,
               "confidence": 60, "entry_price": 1.0}
    await svc._dispatch({
        "user_id": d_user.id, "event_type": EventType.SETUP_DETECTED.value,
        "data": payload, "message": "",
    })
    sent = len(bot.messages) > 0
    return sent, (
        "BUG: alert_service._send_signal references undefined `reasons` "
        "when snapshot is absent (NameError) - text-only fallback never sends"
        if not sent else "ok"
    )


async def alert_dedup():
    from telegram_bot.services.alert_service import AlertService
    from core_engine.events.event_types import EventType

    bot = FakeBot()
    svc = AlertService(bot, renderer=FakeRenderer())
    d_user = await get_user(777004)
    svc._last_sent.clear()
    base = {"user_id": d_user.id, "event_type": EventType.SETUP_DETECTED.value,
            "data": {"symbol": "EURUSD", "direction": "BUY", "score": 60,
                     "snapshot": {"structure": {"bos_detected": True}}},
            "message": ""}
    await svc._dispatch(base)
    first = len(bot.messages)
    await svc._dispatch(base)  # duplicate within cooldown -> dedup
    second = len(bot.messages)
    return (first >= 1 and second == first), f"first={first} second={second}"


async def alert_analysis_callback():
    """ANALYSIS: callback -> renders snapshot + reply_photo."""
    from telegram_bot.services.alert_service import AlertService
    from telegram_bot.handlers.callback_handler import callback_handler

    bot = FakeBot()
    svc = AlertService(bot, renderer=FakeRenderer())
    d_user = await get_user(777004)

    chat = Chat(FakeUser(777004, "dana", "Dana"))
    chat.context.bot_data["alert_service"] = svc

    snapshot = {"structure": {"bos_detected": True}, "drawing": {"buy_sell": "BUY"}}
    key = svc._store_analysis_snapshot(snapshot, {"symbol": "XAUUSD"})
    msg = FakeMessage(chat.chat)
    q = FakeCallbackQuery(bot, msg, f"ANALYSIS:{key}", chat.user)
    upd = FakeUpdate(callback_query=q, user=chat.user)
    await callback_handler(upd, chat.context)
    return len(msg.photo_sent) == 1, f"photos sent: {len(msg.photo_sent)}"


# ================================================================ main


async def main():
    print("Creating QA database + tables...")
    await init_db()
    print("Resetting QA database...")
    await reset_db()
    await seed()
    patch_engine_manager()

    A = Chat(FakeUser(777001, "alice", "Alice"))
    B = Chat(FakeUser(777002, "bob", "Bob"))
    C = Chat(FakeUser(777005, "cara", "Cara"))
    D = Chat(FakeUser(777004, "dana", "Dana"))

    # ---------- Phase 1: journeys ----------
    await qa("WZ-001", "Start + add account (Personal)", lambda: journey_personal(A))
    await qa("WZ-002", "Funded wizard + activation (FTMO)", lambda: journey_funded(D))
    await qa("WZ-003", "First-run + license negatives (User C)", lambda: journey_c_negatives(C))
    await qa("WZ-004", "Language switch AR/EN (User B)", lambda: journey_b_language(B))

    d_account = await _latest_account(777004)

    # ---------- Phase 3: account management + pages ----------
    if d_account:
        acc_id = d_account.id
        await qa("WZ-010", "Account detail / rename / risk / pause / resume / rescan / pages",
                 lambda: journey_d_management(D, acc_id))
        await qa("WZ-011", "Ticket creation (billing)",
                 lambda: _assert_ticket_created(D))

    # ---------- Phase 2: static audits ----------
    await qa("AU-001", "All telegram_bot/commands/* registered in bot.py",
             lambda: audit_command_registration())
    await qa("AU-002", "Every keyboard callback_data has a router branch",
             lambda: audit_callback_coverage())
    await qa("AU-003", "Required router prefixes present",
             lambda: audit_route_literals())

    # ---------- Phase 5: alert notification audit ----------
    await qa("AL-001", "All alert event types deliver a message",
             lambda: alert_audit())
    await qa("AL-002", "Snapshot-less signal text fallback",
             lambda: alert_no_snapshot_bug())
    await qa("AL-003", "Dedup cooldown blocks duplicate signals",
             lambda: alert_dedup())
    await qa("AL-004", "ANALYSIS: callback renders photo",
             lambda: alert_analysis_callback())

    # ---------- Phase 6: report ----------
    await close_db()
    return QA_CTX.report()


# ---------------------------------------------------------------- helpers


async def _latest_account(telegram_id):
    user = await get_user(telegram_id)
    if not user:
        return None
    async with async_session_factory() as s:
        accs = await AccountRepository(s).get_by_user_id(user.id)
    return accs[0] if accs else None


async def _assert_ticket_created(chat: Chat):
    """True only if the ticket flow in journey_d_management created a row."""
    from sqlalchemy import select, func

    user = await get_user(777004)
    if not user:
        return False, "dana (777004) user missing from DB"
    async with async_session_factory() as s:
        count = (await s.execute(
            select(func.count(SupportTicket.id)).where(SupportTicket.user_id == user.id)
        )).scalar() or 0
    if count == 0:
        return False, (
            "BUG: full ticket flow (CREATE -> CAT:billing -> description) "
            "finished without creating a SupportTicket row"
        )
    return True, f"{count} ticket(s) created for dana"


if __name__ == "__main__":
    import asyncio as _asyncio

    async def _wrap():
        return await main()

    passed, failed, errors = _asyncio.run(_wrap())
    sys.exit(1 if (failed or errors) else 0)

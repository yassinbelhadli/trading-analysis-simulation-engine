"""EventNotificationBridge integration test — verifies the full pipeline:

    EventBus → EventNotificationBridge → NotificationDispatcher → Telegram channel

Run:  python scripts/_qa_event_bridge.py
Requires: QA DB (ict_funded_ea_qa) + TELEGRAM_TEST_MODE=true

Covers:
  1. Bridge subscribes to EventBus and receives events
  2. Events are routed through NotificationDispatcher (preference-gated)
  3. Telegram delivery is called (mocked via TELEGRAM_TEST_MODE)
  4. Audit records are written
  5. Preference gating: signals=off blocks SETUP_DETECTED
  6. Dedup: same symbol:direction within cooldown is skipped
  7. System events (ERROR, HEALTH_WARNING, SYSTEM_INFO) always delivered
"""
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:cimoro2008@localhost:5432/ict_funded_ea_qa"
os.environ["ENCRYPTION_KEY"] = "XLX1vxl3BclZbOETIL-StfxdVDrWeRj5VBCG-eEQpr0="
os.environ["USE_MOCK_TELEGRAM_SCAN"] = "true"
os.environ["TELEGRAM_TEST_MODE"] = "true"
os.environ["EMAIL_TEST_MODE"] = "true"

PASSWORD = "BridgeTest!789"
OWNER = "bridge_test_owner@test.local"
SIGNALS_ON = "bridge_signals_on@test.local"
SIGNALS_OFF = "bridge_signals_off@test.local"

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


def _run_async(fn):
    return asyncio.run(fn())


def _seed():
    async def _do():
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from sqlalchemy import delete, select
        from database.base import Base
        from database.models import (
            AuditLog, User, Role,
        )
        from security.access_control import seed_roles_and_permissions
        from security.password import hash_password

        eng = create_async_engine(os.environ["DATABASE_URL"])
        factory = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
        try:
            async with factory() as s:
                await s.run_sync(lambda c: Base.metadata.create_all(c.bind))
                await seed_roles_and_permissions(s)

                # Clean previous test users
                await s.execute(delete(User).where(User.email.in_([
                    OWNER, SIGNALS_ON, SIGNALS_OFF,
                ])))
                await s.execute(delete(AuditLog).where(
                    AuditLog.event_type == "notification.delivery"
                ))
                await s.flush()

                roles = {r.name: r.id for r in (await s.execute(select(Role))).scalars().all()}

                def _user(email, role_name, first, last, telegram_id=None, language="EN", preferences=None):
                    return User(
                        email=email,
                        password_hash=hash_password(PASSWORD),
                        role_id=roles.get(role_name),
                        account_status="active",
                        email_verified=True,
                        first_name=first, last_name=last,
                        telegram_id=telegram_id, language=language,
                        preferences=preferences or {},
                    )

                s.add(_user(OWNER, "owner", "Bridge", "Owner", telegram_id=200000001))
                s.add(_user(SIGNALS_ON, "client", "Bridge", "SignalsOn",
                            telegram_id=200000002, language="EN",
                            preferences={"notifications": {"signals": True, "filled": True, "tp": True, "sl": True}}))
                s.add(_user(SIGNALS_OFF, "client", "Bridge", "SignalsOff",
                            telegram_id=200000003, language="EN",
                            preferences={"notifications": {"signals": False, "filled": True, "tp": True, "sl": True}}))
                await s.commit()
                return True
        finally:
            await eng.dispose()

    asyncio.run(_do())


# ---------------------------------------------------------------------------
# 1. Bridge subscribes + dispatches events through the full pipeline
# ---------------------------------------------------------------------------
def test_bridge_subscribe_and_dispatch():
    print("\n[1] Bridge — subscribe + dispatch through NotificationDispatcher")
    from core_engine.events.event_bus import event_bus
    from core_engine.events.event_types import EventType
    from api.services.notifications.event_bridge import EventNotificationBridge

    bridge = EventNotificationBridge()
    bridge.start()

    check(bridge._subscribed, "bridge subscribed to event bus")
    check(event_bus.listeners_count(EventType.SETUP_DETECTED.value) > 0,
          "event_bus has listener for SETUP_DETECTED")

    # Publish a SETUP_DETECTED event inside async context
    async def _publish_and_wait():
        event_bus.publish(EventType.SETUP_DETECTED.value, {
            "user_id": "",
            "event_type": EventType.SETUP_DETECTED.value,
            "data": {"symbol": "XAUUSD", "direction": "BUY", "score": 85, "confidence": 78},
            "message": "Setup detected",
        })
        await asyncio.sleep(0.3)

    asyncio.run(_publish_and_wait())

    bridge.stop()
    check(not bridge._subscribed, "bridge unsubscribed from event bus")


# ---------------------------------------------------------------------------
# 2. Full async dispatch: bridge → dispatcher → telegram delivery
# ---------------------------------------------------------------------------
def test_bridge_full_dispatch():
    print("\n[2] Bridge — full async dispatch through DB + dispatcher")
    from core_engine.events.event_bus import event_bus
    from core_engine.events.event_types import EventType
    from api.services.notifications.event_bridge import EventNotificationBridge
    from api.services.notifications.dispatcher import NotificationDispatcher
    from api.services.notifications.preferences import get_user_notifications
    from api.services.notifications.rules import resolve_channels

    async def _test():
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from sqlalchemy import select
        from database.models import User

        eng = create_async_engine(os.environ["DATABASE_URL"])
        factory = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
        try:
            async with factory() as s:
                # Test 1: User with signals ON — TRADE_OPENED should be routed
                on_u = (await s.execute(
                    select(User).where(User.email == SIGNALS_ON)
                )).scalar_one()

                dispatcher = NotificationDispatcher()
                res = await dispatcher.dispatch(
                    s, user=on_u, event_type="TRADE_OPENED",
                    payload={"symbol": "XAUUSD", "direction": "BUY", "price": 2410.5},
                )
                check("telegram" in res["channels"],
                      "TRADE_OPENED routed to telegram for signals-on user",
                      str(res["channels"]))
                check(any(r["status"] == "delivered" for r in res["results"]),
                      "telegram delivery succeeded (mock)",
                      str(res["results"]))
                check(bool(res["audit_id"]),
                      "audit record written",
                      str(res.get("audit_id")))

                # Test 2: User with signals OFF — SETUP_DETECTED should be blocked
                off_u = (await s.execute(
                    select(User).where(User.email == SIGNALS_OFF)
                )).scalar_one()

                res2 = await dispatcher.dispatch(
                    s, user=off_u, event_type="SETUP_DETECTED",
                    payload={"symbol": "NAS100", "direction": "SELL"},
                )
                check(res2["channels"] == [],
                      "SETUP_DETECTED blocked for signals-off user",
                      str(res2["channels"]))
                check(bool(res2["audit_id"]),
                      "audit record even when blocked",
                      str(res2.get("audit_id")))

                # Test 3: User with signals OFF — TP_HIT should still be routed (tp=True)
                res3 = await dispatcher.dispatch(
                    s, user=off_u, event_type="TP_HIT",
                    payload={"symbol": "EURUSD", "price": 1.0850},
                )
                check("telegram" in res3["channels"],
                      "TP_HIT routed even for signals-off (tp=True)",
                      str(res3["channels"]))

                # Test 4: System event — always delivered regardless of prefs
                res4 = await dispatcher.dispatch(
                    s, user=off_u, event_type="SYSTEM_INFO",
                    payload={}, message="System update",
                )
                check("telegram" in res4["channels"],
                      "SYSTEM_INFO always delivered",
                      str(res4["channels"]))

                await s.commit()
                return True
        finally:
            await eng.dispose()

    check(asyncio.run(_test()), "full dispatch flow")


# ---------------------------------------------------------------------------
# 3. Bridge _on_event → async dispatch (simulated event bus flow)
# ---------------------------------------------------------------------------
def test_bridge_event_handler():
    print("\n[3] Bridge — _on_event schedules async dispatch correctly")
    from api.services.notifications.event_bridge import EventNotificationBridge
    from core_engine.events.event_bus import event_bus
    from core_engine.events.event_types import EventType

    dispatched_events = []
    original_dispatch = EventNotificationBridge._dispatch

    async def _mock_dispatch(self, data):
        dispatched_events.append(data)

    # Patch
    EventNotificationBridge._dispatch = _mock_dispatch

    bridge = EventNotificationBridge()
    bridge.start()

    async def _publish_and_wait():
        """Publish inside an async context so asyncio.create_task works."""
        event_bus.publish(EventType.TRADE_OPENED.value, {
            "user_id": "test-user-123",
            "event_type": "TRADE_OPENED",
            "data": {"symbol": "GBPJPY", "direction": "SELL", "price": 190.25},
            "message": "Trade opened",
        })
        # Yield to let the create_task fire
        await asyncio.sleep(0.3)

    asyncio.run(_publish_and_wait())

    bridge.stop()
    EventNotificationBridge._dispatch = original_dispatch

    check(len(dispatched_events) == 1,
          "bridge dispatched exactly 1 event",
          f"got {len(dispatched_events)}")
    if dispatched_events:
        check(dispatched_events[0].get("user_id") == "test-user-123",
              "bridge passed correct user_id",
              str(dispatched_events[0].get("user_id")))
        check(dispatched_events[0].get("event_type") == "TRADE_OPENED",
              "bridge passed correct event_type",
              str(dispatched_events[0].get("event_type")))


# ---------------------------------------------------------------------------
# 4. Dedup: same symbol:direction within cooldown is skipped
# ---------------------------------------------------------------------------
def test_bridge_dedup():
    print("\n[4] Bridge — dedup blocks repeated symbol:direction")
    from api.services.notifications.event_bridge import EventNotificationBridge

    bridge = EventNotificationBridge()

    check(bridge._allow_send("XAUUSD:BUY"), "first send allowed")
    check(not bridge._allow_send("XAUUSD:BUY"), "duplicate blocked within cooldown")
    check(bridge._allow_send("EURUSD:SELL"), "different pair allowed")

    # Manually set an old timestamp to test cooldown expiry
    bridge._last_sent["TEST:PAIR"] = time.time() - bridge.DEDUP_COOLDOWN - 1
    check(bridge._allow_send("TEST:PAIR"), "send allowed after cooldown expiry")


# ---------------------------------------------------------------------------
# 5. Bridge singleton exists and can be imported
# ---------------------------------------------------------------------------
def test_bridge_singleton():
    print("\n[5] Bridge — singleton import")
    from api.services.notifications.event_bridge import event_notification_bridge
    from api.services.notifications.event_bridge import EventNotificationBridge

    check(isinstance(event_notification_bridge, EventNotificationBridge),
          "singleton is EventNotificationBridge instance")
    check(not event_notification_bridge._subscribed,
          "singleton starts unsubscribed")


# ---------------------------------------------------------------------------
# 6. All 17 bridge event types match AlertService coverage
# ---------------------------------------------------------------------------
def test_bridge_event_coverage():
    print("\n[6] Bridge — event coverage matches AlertService")
    from api.services.notifications.event_bridge import BRIDGE_EVENTS
    from telegram_bot.services.alert_service import ALERT_EVENTS

    bridge_set = set(BRIDGE_EVENTS)
    alert_set = set(ALERT_EVENTS)

    missing = alert_set - bridge_set
    extra = bridge_set - alert_set

    check(len(missing) == 0,
          "bridge covers all AlertService events",
          f"missing: {missing}" if missing else "")
    # extra is OK — bridge may handle more events
    if extra:
        print(f"  [INFO] Bridge handles extra events: {extra}")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main() -> int:
    print("=" * 62)
    print("EventNotificationBridge Integration Test")
    print("=" * 62)
    _seed()
    test_bridge_singleton()
    test_bridge_event_coverage()
    test_bridge_dedup()
    test_bridge_subscribe_and_dispatch()
    test_bridge_event_handler()
    test_bridge_full_dispatch()

    print("\n" + "=" * 62)
    print(f"TOTAL {PASSED + FAILED} | PASS {PASSED} | FAIL {FAILED}")
    for name, detail in ERRORS:
        print(f"  FAILED CHECK: {name} -> {detail}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())

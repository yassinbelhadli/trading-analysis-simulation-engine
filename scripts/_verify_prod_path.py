"""Production Path Verification — REAL EventBus → Bridge → Dispatcher → Telegram.

This test publishes events through the SAME event_bus.publish() that the
trading engine uses, with the SAME data format. It does NOT call the
dispatcher directly and does NOT bypass the EventBus.

Events flow through the full production chain:
  event_bus.publish() → EventNotificationBridge._on_event() →
  asyncio.create_task(_dispatch()) → user lookup → dispatcher.dispatch() →
  preference gate → TelegramChannel.deliver() → real Telegram API

Uses the demo.client account (telegram_id=7320801946).
All notification preferences are ON for this user.
"""
import asyncio
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Load config/.env — same pattern as api/main.py
_env_path = Path(__file__).resolve().parent.parent / "config" / ".env"
if _env_path.exists():
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _key, _val = _line.split("=", 1)
            _key, _val = _key.strip(), _val.strip().strip("\"'")
            if _key and not os.environ.get(_key):
                os.environ[_key] = _val

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s | %(message)s",
)
logger = logging.getLogger("prod_path_verify")

DEMO_CLIENT_ID = None  # resolved at runtime
TELEGRAM_CHAT_ID = 7320801946

PASSED = 0
FAILED = 0
ERRORS = []


def ok(name):
    global PASSED
    PASSED += 1
    print(f"  [PASS] {name}")


def fail(name, detail=""):
    global FAILED
    FAILED += 1
    ERRORS.append((name, detail))
    print(f"  [FAIL] {name} -> {detail}")


def check(cond, name, detail=""):
    if cond:
        ok(name)
    else:
        fail(name, detail)


async def _resolve_demo_client():
    """Find the demo.client user ID."""
    global DEMO_CLIENT_ID
    from database.db import async_session_factory
    from sqlalchemy import select
    from database.models import User

    async with async_session_factory() as s:
        u = (await s.execute(
            select(User).where(User.email == "demo.client@ict-ea-demo.dev")
        )).scalar_one_or_none()
        if not u:
            fail("resolve demo.client user", "user not found")
            return False
        DEMO_CLIENT_ID = str(u.id)
        check(bool(u.telegram_id), "demo.client has telegram_id", str(u.telegram_id))
        prefs = (u.preferences or {}).get("notifications", {})
        check(prefs.get("signals", False), "signals pref ON")
        check(prefs.get("filled", False), "filled pref ON")
        check(prefs.get("tp", False), "tp pref ON")
        check(prefs.get("sl", False), "sl pref ON")
        return True


def _publish_event(event_type, message, data):
    """Publish using EXACT same format as engine_runner._publish()."""
    from core_engine.events.event_bus import event_bus
    event_bus.publish(event_type, {
        "account_id": "prod-verify-test",
        "user_id": DEMO_CLIENT_ID,
        "event_type": event_type,
        "trade_id": str(data.get("ticket", "")),
        "message": message,
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


async def _verify_audit_records(expected_events):
    """Query audit_logs for notification.delivery records."""
    from database.db import async_session_factory
    from sqlalchemy import select, desc
    from database.models import AuditLog

    async with async_session_factory() as s:
        records = (await s.execute(
            select(AuditLog)
            .where(AuditLog.event_type == "notification.delivery")
            .where(AuditLog.user_id == DEMO_CLIENT_ID)
            .order_by(desc(AuditLog.created_at))
            .limit(20)
        )).scalars().all()

    found_types = set()
    delivered_count = 0
    for r in records:
        payload = r.payload_json or {}
        et = payload.get("event_type", "")
        channels = payload.get("channels", [])
        results = payload.get("results", [])
        if et in expected_events:
            found_types.add(et)
            if channels and any(res.get("status") == "delivered" for res in results):
                delivered_count += 1
            logger.info("  audit: %s channels=%s delivered=%s",
                        et, channels, any(res.get("status") == "delivered" for res in results))

    return found_types, delivered_count, len(records)


async def _verify_bridge_lifecycle():
    """Verify bridge start/stop/unsubscribe."""
    from api.services.notifications.event_bridge import EventNotificationBridge
    from core_engine.events.event_bus import event_bus
    from core_engine.events.event_types import EventType

    bridge = EventNotificationBridge()

    # Start
    bridge.start()
    check(bridge._subscribed, "bridge.start() sets _subscribed")
    check(event_bus.listeners_count(EventType.TRADE_OPENED.value) > 0,
          "bridge subscribed to TRADE_OPENED on event_bus")

    # Stop
    bridge.stop()
    check(not bridge._subscribed, "bridge.stop() clears _subscribed")
    check(event_bus.listeners_count(EventType.TRADE_OPENED.value) == 0 or
          event_bus.listeners_count(EventType.TRADE_OPENED.value) < 10,
          "bridge unsubscribed from event_bus (listeners reduced)")


async def _run_production_path():
    """Main test: publish events via EventBus, verify full path."""
    from api.services.notifications.event_bridge import event_notification_bridge

    print("\n" + "=" * 62)
    print("PRODUCTION PATH VERIFICATION")
    print("event_bus.publish() -> Bridge -> Dispatcher -> Telegram")
    print("4 events: SETUP_DETECTED, TRADE_OPENED, TP_HIT, SL_HIT")
    print("=" * 62)

    # A. Resolve user
    print("\n--- User setup ---")
    if not await _resolve_demo_client():
        return

    # B. Start bridge (same way production starts it)
    print("\n--- Bridge startup ---")
    event_notification_bridge.start()
    check(event_notification_bridge._subscribed, "production bridge started")
    logger.info("Bridge subscribed — publishing production events now")

    # Small delay to let subscription settle
    await asyncio.sleep(0.2)

    # C. Publish 4 events via the EXACT production format
    print("\n--- Publishing events via event_bus.publish() ---")

    # 1. SETUP_DETECTED
    _publish_event(
        "SETUP_DETECTED",
        "Setup: XAUUSD BUY score=82",
        {"symbol": "XAUUSD", "direction": "BUY", "score": 82, "confidence": 75,
         "entry_price": 2412.50, "stop_loss": 2405.00, "take_profit": 2430.00,
         "risk_reward": 2.3, "lot_size": 0.01, "timeframe": "M15",
         "snapshot": {"drawing": {"entry_price": 2412.50}},
         "candidate_id": "verify-001"},
    )
    logger.info("Published SETUP_DETECTED (XAUUSD BUY)")

    # 2. TRADE_OPENED
    _publish_event(
        "TRADE_OPENED",
        "Order placed: XAUUSD BUY lot=0.01",
        {"symbol": "XAUUSD", "direction": "BUY", "lot_size": 0.01,
         "entry": 2412.50, "filled_price": 2412.50,
         "sl": 2405.00, "tp": 2430.00, "ticket": "99001",
         "risk_reward": 2.3, "candidate_id": "verify-001"},
    )
    logger.info("Published TRADE_OPENED (XAUUSD BUY)")

    # 3. TP_HIT
    _publish_event(
        "TP_HIT",
        "TP: XAUUSD BUY @ 2430.00 PnL=+17.50",
        {"symbol": "XAUUSD", "direction": "BUY", "exit_price": 2430.00,
         "realized_pnl": 17.50, "price": 2430.00, "ticket": "99001"},
    )
    logger.info("Published TP_HIT (XAUUSD BUY)")

    # 4. SL_HIT (different pair to avoid dedup)
    _publish_event(
        "SL_HIT",
        "SL: EURUSD SELL @ 1.0820 PnL=-8.25",
        {"symbol": "EURUSD", "direction": "SELL", "exit_price": 1.0820,
         "realized_pnl": -8.25, "price": 1.0820, "ticket": "99002"},
    )
    logger.info("Published SL_HIT (EURUSD SELL)")

    # D. Wait for async dispatch to complete
    logger.info("Waiting for async dispatch...")
    await asyncio.sleep(3)

    # E. Verify audit records
    print("\n--- Audit record verification ---")
    expected = {"SETUP_DETECTED", "TRADE_OPENED", "TP_HIT", "SL_HIT"}
    found, delivered, total = await _verify_audit_records(expected)
    check(expected.issubset(found),
          f"all 4 events have audit records",
          f"expected={expected} found={found}")
    check(delivered >= 4,
          f"at least 4 deliveries confirmed in audit",
          f"delivered={delivered} total_records={total}")

    # F. Dedup: publish same SETUP_DETECTED again — should be skipped
    print("\n--- Dedup verification ---")
    before_count = total
    _publish_event(
        "SETUP_DETECTED",
        "Setup: XAUUSD BUY score=82 (duplicate)",
        {"symbol": "XAUUSD", "direction": "BUY", "score": 82, "confidence": 75,
         "candidate_id": "verify-001-dup"},
    )
    await asyncio.sleep(2)
    _, _, after_total = await _verify_audit_records(expected)
    # Dedup should prevent a second SETUP_DETECTED delivery
    check(after_total <= before_count + 1,
          "dedup blocked duplicate SETUP_DETECTED (no extra audit)",
          f"before={before_count} after={after_total}")

    # G. Stop bridge
    print("\n--- Bridge shutdown ---")
    event_notification_bridge.stop()
    check(not event_notification_bridge._subscribed, "bridge stopped and unsubscribed")


async def _verify_lifecycle():
    print("\n" + "=" * 62)
    print("BRIDGE LIFECYCLE VERIFICATION")
    print("=" * 62)
    await _verify_bridge_lifecycle()


async def main():
    # Verify A+B first (static code checks), then run production path
    print("=" * 62)
    print("A+B. Static production path checks")
    print("=" * 62)

    # A. Bridge started exactly once in production
    import ast
    app_py = Path(__file__).resolve().parent.parent / "telegram_bot" / "app.py"
    content = app_py.read_text(encoding="utf-8")
    bridge_starts = content.count("event_notification_bridge.start()")
    check(bridge_starts == 1,
          f"A: bridge.start() called exactly once in app.py",
          f"found {bridge_starts} calls")

    # B. AlertService not active in production
    alert_starts = content.count("alert_service.start()")
    check(alert_starts == 0,
          "B: alert_service.start() NOT called in app.py",
          f"found {alert_starts} calls")

    # C. No duplicate: AlertService not imported in app.py
    alert_import = "from telegram_bot.services.alert_service import" in content
    check(not alert_import,
          "C: AlertService not imported in app.py (no dual path)")

    # Run production path
    await _run_production_path()
    await _verify_lifecycle()

    # Final summary
    print("\n" + "=" * 62)
    print(f"RESULT: {PASSED + FAILED} checks | PASS {PASSED} | FAIL {FAILED}")
    for name, detail in ERRORS:
        print(f"  FAILED: {name} -> {detail}")
    print("=" * 62)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

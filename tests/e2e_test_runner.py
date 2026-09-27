"""E2E Test Runner — starts bot + engine + monitors signals.

Usage:
    python tests/e2e_test_runner.py

Output is written to e2e_test.log and printed to stdout.
"""
import asyncio, logging, sys, os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("e2e_test.log", mode="w"),
    ],
)
logger = logging.getLogger("e2e")


async def main():
    # ── 1. Start EventNotificationBridge (Telegram notifications via dispatcher) ──
    from api.services.notifications.event_bridge import event_notification_bridge

    event_notification_bridge.start()
    logger.info("EventNotificationBridge started — listening for trade events")

    # ── 2. Start EngineRunner for active accounts ──
    from core_engine.engine_runner import engine_runner
    from core_engine.engine_manager import engine_manager
    from database.db import async_session_factory
    from sqlalchemy import select
    from database.models import TradingAccount

    logger.info("Starting EngineRunner...")
    async with async_session_factory() as session:
        stmt = select(TradingAccount).where(TradingAccount.active == True)
        result = await session.execute(stmt)
        accounts = list(result.scalars().all())

    if not accounts:
        logger.warning("No active trading accounts found in DB!")
        logger.info("Will wait 60s for any signals...")
    else:
        for acc in accounts:
            logger.info(f"Starting engine for account {acc.id} ({acc.login} @ {acc.server})")
            await engine_manager.start(acc.id)
            await engine_runner.start_engine(acc.id, acc.user_id)
        logger.info(f"Engine runner started for {len(accounts)} account(s)")

    # ── 3. Send Telegram notification ──
    try:
        from api.services.notifications.channels import TelegramChannel
        chat_id = int(os.getenv("TELEGRAM_CHAT_ID", "7320801946"))
        tg = TelegramChannel()
        res = await tg.deliver(chat_id=chat_id, text=(
            "\U0001f916 ICT Funded EA Pro — E2E Test\n"
            f"Engine: {'Running' if accounts else 'No accounts'}\n"
            "Monitoring for signals..."
        ))
        logger.info("Telegram notification sent: %s", res.status)
    except Exception as e:
        logger.warning(f"Could not send Telegram notification: {e}")

    # ── 4. Monitor for signals (runs 10 min) ──
    signal_count = 0
    for i in range(60):  # 60 iterations × 10s = 10 min
        await asyncio.sleep(10)
        # Check engine status
        statuses = {aid: engine_manager.get_status(aid) for aid in list(engine_runner._tasks.keys())}
        for aid, st in statuses.items():
            if st.state in ("SIGNAL_DETECTED", "TRADE_EXECUTED"):
                signal_count += 1
        if i % 6 == 0:  # Every minute
            logger.info(f"Monitoring... ({i//6+1}/10 min) | Engines: {len(statuses)}")

    # ── 5. Summary ──
    logger.info(f"\n{'='*60}")
    logger.info(f"E2E Test Complete — {signal_count} signals detected")
    logger.info(f"{'='*60}")

    # ── 6. Cleanup ──
    event_notification_bridge.stop()
    await engine_runner.stop_all()


if __name__ == "__main__":
    asyncio.run(main())

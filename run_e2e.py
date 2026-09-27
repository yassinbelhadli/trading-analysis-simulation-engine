"""Bootstrap: starts Telegram bot + EngineRunner for E2E testing."""
import asyncio, logging, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("e2e.log")],
)
logger = logging.getLogger("e2e")

async def main():
    # Start Telegram bot
    logger.info("Starting Telegram bot...")
    from telegram_bot.bot import TelegramApplication
    bot_app = TelegramApplication()

    # Start engine for active accounts
    logger.info("Starting EngineRunner...")
    from core_engine.engine_runner import engine_runner
    from core_engine.engine_manager import engine_manager
    from database.db import async_session_factory
    from sqlalchemy import select
    from database.models import TradingAccount

    async with async_session_factory() as session:
        stmt = select(TradingAccount).where(TradingAccount.active == True)
        result = await session.execute(stmt)
        accounts = list(result.scalars().all())
        logger.info(f"Found {len(accounts)} active trading account(s)")
        for acc in accounts:
            logger.info(f"  Account: {acc.id} | {acc.login} | {acc.server}")
            await engine_manager.start(acc.id)
            await engine_runner.start_engine(acc.id, acc.user_id)

    # Run bot (blocks)
    logger.info("Ready. Starting bot polling...")
    bot_app.run()

if __name__ == "__main__":
    asyncio.run(main())

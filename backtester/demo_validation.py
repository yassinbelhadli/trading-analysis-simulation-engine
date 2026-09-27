"""
Demo Forward Validation Runner — Sprint 16.1

Usage:
    python -m backtester.demo_validation

Starts Telegram bot with lifecycle validation.
Monitors every trade through: DETECTED->PLANNED->SENT->FILLED->BE/PARTIAL/TRAIL->CLOSED
Auto-stops after: 50 trades | 100 signals | 8 hours
Reports: lifecycle CSV, metrics JSON, event replay JSONL
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from telegram_bot.bot import TelegramApplication
from core_engine.validation.harness import DemoValidationHarness, ValidationConfig
from core_engine.validation.harness import harness as validation_harness
from core_engine.engine_runner import engine_runner
from core_engine.scanner import account_scanner
from core_engine.health.health_monitor import health_monitor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("demo_validation")


class DemoValidationApp(TelegramApplication):
    def __init__(self):
        stale_minutes = int(os.environ.get("STALE_MINUTES", "15"))
        config = ValidationConfig(
            enabled=True,
            target_trades=50,
            target_signals=100,
            max_hours=8.0,
            report_interval_sec=600,
            output_dir="data/validation",
            replay_dir="data/validation/replay",
            stale_trade_minutes=stale_minutes,
        )
        validation_harness.config = config
        validation_harness.set_stop_callback(self._auto_stop)
        super().__init__()

    async def _post_init(self, app):
        logger.info("=" * 60)
        logger.info("DEMO VALIDATION MODE — Sprint 16.1")
        logger.info("Target: %d complete trades or %d signals or %.1fh runtime",
                    validation_harness.config.target_trades,
                    validation_harness.config.target_signals,
                    validation_harness.config.max_hours)
        logger.info("Lifecycle: DETECTED->PLANNED->SENT->FILLED->BE/PARTIAL/TRAIL->CLOSED")
        logger.info("=" * 60)

        validation_harness.start()
        await validation_harness.start_background_tasks()

        await super()._post_init(app)
        logger.info("Validation harness active — monitoring all trades")

    async def _post_shutdown(self, app):
        logger.info("Shutting down validation harness...")
        await validation_harness.stop()
        print("\n" + validation_harness.report())
        await super()._post_shutdown(app)
        logger.info("Demo validation complete. Check data/validation/ for reports.")

    async def _auto_stop(self):
        logger.info("Auto-stop: shutting down all systems gracefully...")
        print("\n[AUTO-STOP] Graceful shutdown started")

        print("Stopping engine runner...")
        await engine_runner.stop_all()

        print("Stopping scanners...")
        await account_scanner.stop_all()

        print("Stopping health monitor...")
        health_monitor.stop()

        print("Shutdown complete. Exit code 0.")
        os._exit(0)

    def run(self):
        print("=" * 60)
        print("ICT Funded EA Pro — Demo Validation Mode")
        print("=" * 60)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.app.initialize())
        loop.run_until_complete(self._post_init(self.app))
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            pass
        finally:
            loop.run_until_complete(self._post_shutdown(self.app))


if __name__ == "__main__":
    DemoValidationApp().run()

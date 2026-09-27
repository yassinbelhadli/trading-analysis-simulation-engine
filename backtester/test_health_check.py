import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from monitoring.logs.health_check import health_check

health_check.update("MT5", True, "Connected")
health_check.update("Telegram", True, "Connected")
health_check.update("News", False, "ForexFactory Offline")

print(health_check.summary())
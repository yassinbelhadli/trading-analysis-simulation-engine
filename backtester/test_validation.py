import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from core_engine.validation.lifecycle_tracker import LifecycleTracker, LifecycleStage
from core_engine.validation.event_listener import ValidationEventListener
from core_engine.validation.harness import DemoValidationHarness, ValidationConfig, harness

# Test 1: Basic lifecycle
tracker = LifecycleTracker()
sid = tracker.track_setup("acc1", "user1", "XAUUSD", "BUY", "setup_001")
assert tracker.get_trade("setup_001") is not None
assert tracker._total_setups == 1

tracker.track_planned("setup_001")
tracker.track_sent("setup_001")
tracker.track_filled("setup_001", "12345")
tracker.track_be("12345")
tracker.track_closed("12345")

trade = tracker.get_trade("setup_001")
assert trade.status == "COMPLETE", f"Expected COMPLETE got {trade.status}"
print(f"Test 1 PASS: Lifecycle complete -> {trade.status}")
print(f"  Steps: {' -> '.join(s.stage.value for s in trade.steps)}")

# Test 2: Invalid transition (CLOSED -> BE)
bad_sid = tracker.track_setup("acc1", "user1", "XAUUSD", "SELL", "bad_001")
tracker.track_sent("bad_001")
tracker.track_closed("bad_001")
tracker.track_be("bad_001")
bad = tracker.get_trade("bad_001")
assert bad.failed, "Expected failed trade"
print(f"Test 2 PASS: Invalid transition detected -> {bad.fail_reason}")

# Test 3: Timeout (simulate by setting old timestamp)
t_sid = tracker.track_setup("acc1", "user1", "XAUUSD", "BUY", "timeout_001")
trade = tracker.get_trade("timeout_001")
from datetime import timezone, timedelta
trade.steps[0].timestamp = trade.steps[0].timestamp - timedelta(seconds=120)
stale = tracker.check_timeouts()
assert len(stale) > 0, "Expected stale trades"
print(f"Test 3 PASS: Timeout detected -> {stale[0]}")

# Test 4: Summary
summary = tracker.summary()
assert summary["total"] > 0
assert summary["failed"] >= 1
assert summary["complete"] >= 1
print(f"Test 4 PASS: Summary -> total={summary['total']} complete={summary['complete']} failed={summary['failed']}")

print("\nAll validation tests PASSED")

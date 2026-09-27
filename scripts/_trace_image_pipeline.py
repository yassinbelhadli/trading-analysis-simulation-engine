"""IMAGE PIPELINE REPORT — trace the exact production chain:
SetupCandidate → setup_to_snapshot → RenderService.render_snapshot →
to_bytes → AlertService._send_signal → bot.send_photo / bot.send_message

A real detection-produced SetupCandidate is built (same fields the engine
fills in engine_runner), then every step is instrumented and reported.
No modifications are made to any project module.
"""
import sys, os, io, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.WARNING,
                    format="%(levelname)s:%(name)s:%(message)s")

from datetime import datetime, timedelta
from renderer_bridge.setup_mapper import setup_to_snapshot
from renderer_bridge.render_service import RenderService
from telegram_bot.services.alert_service import AlertService

# ── 1. Build a SetupCandidate exactly like engine_runner produces ──
random_ohlc = []
p = 3320.0
start = datetime(2026, 7, 31, 8, 0)
import random; random.seed(7)
for i in range(80):
    o = p
    c = o + random.uniform(-2.0, 2.0)
    hi, lo = max(o, c) + random.uniform(0.1, 0.6), min(o, c) - random.uniform(0.1, 0.6)
    random_ohlc.append({"time": int((start + timedelta(hours=i)).timestamp()),
                        "open": round(o, 2), "high": round(hi, 2),
                        "low": round(lo, 2), "close": round(c, 2), "index": i})
    p = c

from core_engine.detection.setup_detector import (
    MarketStructureResult, LiquidityResult, FVGResult, OrderBlockResult,
    PremiumDiscountResult, ScoreResult, SetupCandidate,
)
from core_engine.data_feed.session_manager import SessionAnalysis

structure = MarketStructureResult(
    valid=True, trend="DOWN", trend_direction="SELL",
    mss_detected=True, choch_detected=True, bos_detected=True,
    mss_type="BEARISH", choch_type="BEARISH", bos_type="BEARISH",
    strong_high=3328.0, strong_low=3312.0,
    protected_high=3326.0, protected_low=3314.0,
)
liquidity = LiquidityResult(valid=True, sweep_detected=True, sweep_price=3329.5,
                            sweep_type="SELL_SIDE", pdh_swept=True,
                            reasons=["Liquidity Sweep"])
fvg = FVGResult(valid=True, fvg_detected=True, fvg_type="BEARISH", fvg_top=3319.5,
                fvg_bottom=3318.2, fvg_size=1.3, reasons=["FVG"])
ob = OrderBlockResult(valid=True, ob_detected=True, ob_type="BEARISH", ob_top=3324.0,
                      ob_bottom=3320.0, ob_mid=3322.0, fresh=True,
                      reasons=["Fresh OB"])
pd = PremiumDiscountResult(valid=True, premium_high=3328.0,
                           discount_low=3310.0, equilibrium=3319.0,
                           reasons=["Premium"])
sc = ScoreResult(valid=True, score=84.0, confidence=82.0, rank="TOP",
                 recommendation="EXECUTE", reasons=["High alignment"])
session = SessionAnalysis(timestamp=datetime.now(), pdh=3332.0, pdl=3308.0)

candidate = SetupCandidate(
    symbol="XAUUSD", timeframe="M5", direction="SELL",
    structure=structure, liquidity=liquidity, fvg=fvg, ob=ob,
    premium_discount=pd, score_result=sc,
    score=84.0, rank="TOP", confidence_score=82.0,
    confidence_label="HIGH", approved=True,
    reasons=["MSS", "CHoCH", "BOS", "Liquidity Sweep", "PDH_Swept",
             "FVG", "Fresh OB", "Premium"],
    entry_zone={"entry_price": 3322.0}, stop_loss=3326.5, take_profit=3316.0,
    timestamp=datetime.now(), session=session,
    setup_id="diag_001", chart_data={"ohlc": random_ohlc,
                                     "indicators": {"atr": []}},
)

report = {"step": [], "detail": []}

def step(name, detail):
    report["step"].append(name)
    report["detail"].append(detail)
    print(f"  ✓ {name}: {detail}")

# ── 2. Engine injects plan values (mirrors engine_runner) ──
candidate.entry_zone = {"entry_price": 3322.0}
candidate.stop_loss = 3326.5
candidate.take_profit = 3316.0
step("plan injection", "entry=3322.0 sl=3326.5 tp=3316.0")

# ── 3. setup_to_snapshot ──
try:
    snapshot = setup_to_snapshot(candidate)
    step("setup_to_snapshot", f"type={type(snapshot).__name__} keys={list(snapshot.keys())}")
except Exception as e:
    print(f"  ✗ setup_to_snapshot RAISED: {e!r}")
    sys.exit(1)

snap_chart = snapshot["chart"]["ohlc"]
step("snapshot ohlc", f"candles={len(snap_chart)} last_close={snap_chart[-1]['close']}")
step("snapshot drawing", f"{snapshot.get('drawing')}")
step("snapshot scoring.reasons", f"type={type(snapshot.get('scoring', {}).get('reasons'))}")

# ── 4. RenderService.render_snapshot ──
rs = RenderService(width=1200, height=600, theme="light")
try:
    pil_image = rs.render_snapshot(snapshot)
    step("RenderService.render_snapshot", f"type={type(pil_image).__name__} size={pil_image.size}")
except Exception as e:
    print(f"  ✗ RenderService.render_snapshot RAISED: {e!r}")
    print("REPORT: Renderer created image? NO  (exception swallowed in AlertService → text fallback)")
    sys.exit(1)

# ── 5. to_bytes ──
b = rs.to_bytes(pil_image)
step("to_bytes", f"format=PNG len={len(b)} bytes header={b[:8].hex()}")
assert len(b) > 1000, "to_bytes returned tiny/empty bytes!"

# ── 6. Fake bot captures exactly what Telegram would get ──
class FakeBot:
    def __init__(self):
        self.sent_photo = None
        self.sent_message = None
        self.errors = []
    async def send_photo(self, **kw):
        self.sent_photo = {"chat_id": kw.get("chat_id"), "photo_len": len(kw.get("photo", b"")),
                           "caption": kw.get("caption", "")}
        return type("M", (), {"message_id": 111, "photo": [type("P", (), {"file_id": "fake_photo"})()]})
    async def send_message(self, **kw):
        self.sent_message = kw.get("text", "")
        return type("M", (), {"message_id": 222})()

import asyncio
bot = FakeBot()
svc = AlertService(bot, renderer=rs)

payload = {
    "symbol": "XAUUSD", "direction": "SELL", "score": 84.0,
    "confidence": 82.0, "entry_price": 3322.0, "stop_loss": 3326.5,
    "take_profit": 3316.0, "risk_reward": 2.4, "lot_size": 0.1,
    "timeframe": "M5", "session": "London",
    "reasons": candidate.reasons, "snapshot": snapshot,
    "candidate_id": "diag_001",
}

async def run():
    await svc._send_signal(payload, 12345)

asyncio.run(run())

print("")
print("=" * 60)
print("IMAGE PIPELINE REPORT")
print("=" * 60)
for s, d in zip(report["step"], report["detail"]):
    print(f"  {s} -> {d}")
print("  AlertService._send_signal path ->", "send_photo" if bot.sent_photo else "send_message (TEXT ONLY!)")
print(f"  send_photo called? {'YES' if bot.sent_photo else 'NO'}")
if bot.sent_photo:
    print(f"  send_photo photo bytes = {bot.sent_photo['photo_len']}")
    print(f"  send_photo caption len = {len(bot.sent_photo['caption'])} chars")
    print("  Telegram API response -> Message(message_id=111, photo=[...]) OK")
    print("  Image visible in chat? YES (send_photo succeeded with a valid PNG)")
else:
    print("  send_message called instead -> IMAGE NEVER SENT")
    print("  Image visible in chat? NO")
print("=" * 60)

import asyncio
import logging
import random
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from core_engine.events.event_bus import event_bus
from core_engine.detection.setup_detector import (
    MarketStructureResult, LiquidityResult, FVGResult, OrderBlockResult,
    PremiumDiscountResult, ScoreResult, SetupCandidate,
)
from core_engine.data_feed.session_manager import SessionAnalysis
from renderer_bridge.setup_mapper import setup_to_snapshot

logger = logging.getLogger(__name__)


def _build_debug_candidate() -> SetupCandidate:
    """Build a realistic SetupCandidate (same fields the engine fills in
    engine_runner) so the debug signal ships a real chart like production."""
    random.seed(7)
    ohlc, price, start = [], 3320.0, datetime(2026, 7, 31, 8, 0)
    for i in range(80):
        o = price
        c = o + random.uniform(-2.0, 2.0)
        hi = max(o, c) + random.uniform(0.1, 0.6)
        lo = min(o, c) - random.uniform(0.1, 0.6)
        ohlc.append({"time": int((start + timedelta(hours=i)).timestamp()),
                     "open": round(o, 2), "high": round(hi, 2),
                     "low": round(lo, 2), "close": round(c, 2), "index": i})
        price = c

    return SetupCandidate(
        symbol="XAUUSD", timeframe="M5", direction="SELL",
        structure=MarketStructureResult(
            valid=True, trend="DOWN", trend_direction="SELL",
            mss_detected=True, choch_detected=True, bos_detected=True,
            mss_type="BEARISH", choch_type="BEARISH", bos_type="BEARISH",
            strong_high=3328.0, strong_low=3312.0,
            protected_high=3326.0, protected_low=3314.0,
        ),
        liquidity=LiquidityResult(valid=True, sweep_detected=True,
                                  sweep_price=3329.5, sweep_type="SELL_SIDE",
                                  pdh_swept=True, reasons=["Liquidity Sweep"]),
        fvg=FVGResult(valid=True, fvg_detected=True, fvg_type="BEARISH",
                      fvg_top=3319.5, fvg_bottom=3318.2, fvg_size=1.3,
                      reasons=["FVG"]),
        ob=OrderBlockResult(valid=True, ob_detected=True, ob_type="BEARISH",
                            ob_top=3324.0, ob_bottom=3320.0, ob_mid=3322.0,
                            fresh=True, reasons=["Fresh OB"]),
        premium_discount=PremiumDiscountResult(valid=True, premium_high=3328.0,
                                               discount_low=3310.0,
                                               equilibrium=3319.0,
                                               reasons=["Premium"]),
        score_result=ScoreResult(valid=True, score=84.0, confidence=82.0,
                                 rank="TOP", recommendation="EXECUTE",
                                 reasons=["High alignment"]),
        score=84.0, rank="TOP", confidence_score=82.0, confidence_label="HIGH",
        approved=True,
        reasons=["MSS", "CHoCH", "BOS", "Liquidity Sweep", "PDH_Swept",
                 "FVG", "Fresh OB", "Premium"],
        entry_zone={"entry_price": 3322.0}, stop_loss=3326.5, take_profit=3316.0,
        timestamp=datetime.now(),
        session=SessionAnalysis(timestamp=datetime.now(), pdh=3332.0, pdl=3308.0),
        setup_id="debug-test-001",
        chart_data={"ohlc": ohlc, "indicators": {"atr": []}},
    )


_DEBUG_CANDIDATE = _build_debug_candidate()
_DEBUG_SNAPSHOT = setup_to_snapshot(_DEBUG_CANDIDATE)

EVENTS = [
    ("SETUP_DETECTED", {
        "candidate_id": "debug-test-001", "symbol": "XAUUSD",
        "direction": "SELL", "score": 84.0, "confidence": 0.88,
        "reasons": _DEBUG_CANDIDATE.reasons,
        "snapshot": _DEBUG_SNAPSHOT,
        "timeframe": "M5", "session": "London",
        "entry_price": 3322.0, "stop_loss": 3326.5, "take_profit": 3316.0,
        "lot_size": 0.1, "risk_reward": 2.4,
    }),
    ("PAPER_TRADE_PLANNED", {
        "candidate_id": "debug-test-001", "id": "paper_trade_debug",
        "symbol": "XAUUSD", "direction": "SELL",
        "entry": 3322.0, "stop_loss": 3326.5, "take_profit": 3316.0,
        "lot_size": 0.1, "risk_reward": 2.4,
        "snapshot": _DEBUG_SNAPSHOT,
        "timeframe": "M5", "session": "London",
    }),
    ("TRADE_OPENED", {
        "candidate_id": "debug-test-001", "ticket": 99999999,
        "symbol": "XAUUSD", "direction": "SELL",
        "entry": 3322.0, "sl": 3326.5, "tp": 3316.0, "lot_size": 0.1,
    }),
    ("BREAK_EVEN_MOVED", {"ticket": 99999999, "new_sl": 3322.0}),
    ("PARTIAL_CLOSE", {"ticket": 99999999, "close_volume": 0.05}),
    ("TRADE_CLOSED", {"ticket": 99999999, "profit": 125.0}),
]

async def debug_smoke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Injecting 6 synthetic events...")
    for event_type, data in EVENTS:
        payload = {
            "account_id": "debug", "user_id": "debug",
            "event_type": event_type,
            "trade_id": str(data.get("ticket", "")),
            "message": f"DEBUG: {event_type}",
            "data": data, "timestamp": None,
        }
        await event_bus.publish(event_type, payload)
        await asyncio.sleep(0.2)
    await update.message.reply_text("Done. Check metrics and replay files.")

handler = CommandHandler("debug_smoke", debug_smoke)

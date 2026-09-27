from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

import pandas as pd

from core_engine.data_feed.market_data import MarketData
from core_engine.config.detection.market_structure import MarketStructureDetector
from core_engine.config.detection.liquidity import LiquidityEngine
from core_engine.config.detection.fair_value_gap import FVGDetector
from core_engine.config.detection.volume_imbalance import VolumeImbalanceDetector
from core_engine.config.detection.liquidity_void import LiquidityVoidDetector
from core_engine.config.detection.order_blocks import OrderBlockEngine
from core_engine.config.detection.premium_discount import PremiumDiscountDetector
from core_engine.config.detection.support_resistance import SupportResistanceDetector
from core_engine.config.detection.candle_patterns import CandlePatternDetector
from core_engine.scoring.score_engine import ScoreEngine
from core_engine.scoring.setup_ranker import SetupRanker
from core_engine.scoring.confidence_score import ConfidenceScoreEngine
from core_engine.data_feed.session_manager import SessionAnalysis


COLUMN_MAP = {
    "open": "Open", "high": "High", "low": "Low", "close": "Close",
    "tick_volume": "Tick_Volume", "spread": "Spread",
}


@dataclass
class LiquidityResult:
    valid: bool
    sweep_detected: bool = False
    sweep_type: Optional[str] = None
    sweep_price: Optional[float] = None
    sweep_strength: float = 0.0
    liquidity_source: Optional[str] = None
    liquidity_rank: float = 0.0
    equal_highs: bool = False
    equal_lows: bool = False
    pdh_swept: bool = False
    pdl_swept: bool = False
    asian_high_swept: bool = False
    asian_low_swept: bool = False
    reasons: List[str] = field(default_factory=list)


@dataclass
class FVGResult:
    valid: bool
    fvg_detected: bool = False
    fvg_type: Optional[str] = None
    fvg_top: Optional[float] = None
    fvg_bottom: Optional[float] = None
    fvg_size: Optional[float] = None
    mitigated: bool = False
    reasons: List[str] = field(default_factory=list)


@dataclass
class OrderBlockResult:
    valid: bool
    ob_detected: bool = False
    ob_type: Optional[str] = None
    ob_top: Optional[float] = None
    ob_bottom: Optional[float] = None
    ob_mid: Optional[float] = None
    mitigated: bool = False
    fresh: bool = False
    reasons: List[str] = field(default_factory=list)


@dataclass
class PremiumDiscountResult:
    valid: bool
    zone: Optional[str] = None
    equilibrium: Optional[float] = None
    premium_high: Optional[float] = None
    discount_low: Optional[float] = None
    price_position: Optional[float] = None
    reasons: List[str] = field(default_factory=list)


@dataclass
class ScoreResult:
    valid: bool
    score: float
    confidence: float
    rank: str
    recommendation: str
    breakdown: Dict[str, float] = field(default_factory=dict)
    reasons: List[str] = field(default_factory=list)


@dataclass
class MarketStructureResult:
    valid: bool
    trend: str
    trend_direction: Optional[str]
    bos_detected: bool = False
    choch_detected: bool = False
    mss_detected: bool = False
    bos_type: Optional[str] = None
    choch_type: Optional[str] = None
    mss_type: Optional[str] = None
    structure_id: Optional[str] = None
    protected_high: Optional[float] = None
    protected_low: Optional[float] = None
    sweep_detected: bool = False
    sweep_price: Optional[float] = None
    sweep_type: Optional[str] = None
    consecutive_bos: Optional[int] = None
    strong_high: Optional[float] = None
    strong_low: Optional[float] = None
    weak_high: Optional[float] = None
    weak_low: Optional[float] = None


@dataclass
class SetupCandidate:
    symbol: str
    timeframe: str
    direction: str
    structure: MarketStructureResult
    liquidity: Optional[LiquidityResult] = None
    fvg: Optional[FVGResult] = None
    ob: Optional[OrderBlockResult] = None
    premium_discount: Optional[PremiumDiscountResult] = None
    score_result: Optional[ScoreResult] = None
    score: float = 0.0
    rank: str = "IGNORE"
    confidence_score: float = 0.0
    confidence_label: str = "NO_TRADE"
    approved: bool = False
    reasons: List[str] = field(default_factory=list)
    entry_zone: Optional[Dict[str, float]] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    timestamp: Optional[datetime] = None
    session: Optional[SessionAnalysis] = None
    setup_id: Optional[str] = None
    reject_reason: Optional[str] = None
    chart_data: Optional[Dict[str, Any]] = None

    def _to_json_val(self, v: Any) -> Any:
        """Recursively convert to JSON-safe types."""
        if isinstance(v, datetime):
            return v.isoformat()
        if isinstance(v, Enum):
            return v.value
        if hasattr(v, "__dataclass_fields__"):
            return {f: self._to_json_val(getattr(v, f)) for f in v.__dataclass_fields__}
        if isinstance(v, dict):
            return {k: self._to_json_val(v) for k, v in v.items()}
        if isinstance(v, (list, tuple)):
            return [self._to_json_val(x) for x in v]
        if isinstance(v, (int, float, str, bool)) or v is None:
            return v
        return str(v)

    def to_snapshot(self) -> Dict[str, Any]:
        """Serialize full candidate state into a structured JSON-safe TradingSnapshot dict."""

        exec_data = {}
        if self.entry_zone:
            exec_data["entry_zone"] = dict(self.entry_zone)
        if self.stop_loss is not None:
            exec_data["stop_loss"] = self.stop_loss
        if self.take_profit is not None:
            exec_data["take_profit"] = self.take_profit

        struct = self.structure
        liq = self.liquidity
        fvg_r = self.fvg
        ob_r = self.ob
        pd_r = self.premium_discount
        sc_r = self.score_result
        sess = self.session

        return {
            "metadata": {
                "snapshot_version": "1.0",
                "created_at": datetime.utcnow().isoformat(),
                "setup_id": self.setup_id,
                "symbol": self.symbol,
                "timeframe": self.timeframe,
                "timestamp": self._to_json_val(self.timestamp),
                "reject_reason": self.reject_reason,
            },
            "market": {},
            "structure": {
                "trend": struct.trend if struct else None,
                "trend_direction": struct.trend_direction if struct else None,
                "bos_detected": struct.bos_detected if struct else False,
                "choch_detected": struct.choch_detected if struct else False,
                "mss_detected": struct.mss_detected if struct else False,
                "bos_type": struct.bos_type if struct else None,
                "choch_type": struct.choch_type if struct else None,
                "mss_type": struct.mss_type if struct else None,
                "swing_high": struct.strong_high if struct else None,
                "swing_low": struct.strong_low if struct else None,
                "protected_high": struct.protected_high if struct else None,
                "protected_low": struct.protected_low if struct else None,
                "weak_high": struct.weak_high if struct else None,
                "weak_low": struct.weak_low if struct else None,
                "consecutive_bos": struct.consecutive_bos if struct else None,
            } if struct else {},
            "liquidity": {
                "sweep_detected": liq.sweep_detected if liq else False,
                "sweep_type": liq.sweep_type if liq else None,
                "sweep_price": liq.sweep_price if liq else None,
                "sweep_strength": liq.sweep_strength if liq else 0.0,
                "liquidity_source": liq.liquidity_source if liq else None,
                "liquidity_rank": liq.liquidity_rank if liq else 0.0,
                "equal_highs": liq.equal_highs if liq else False,
                "equal_lows": liq.equal_lows if liq else False,
                "pdh_swept": liq.pdh_swept if liq else False,
                "pdl_swept": liq.pdl_swept if liq else False,
                "asian_high_swept": liq.asian_high_swept if liq else False,
                "asian_low_swept": liq.asian_low_swept if liq else False,
            } if liq else {},
            "order_blocks": [{
                "type": ob_r.ob_type,
                "top": ob_r.ob_top,
                "bottom": ob_r.ob_bottom,
                "mid": ob_r.ob_mid,
                "mitigated": ob_r.mitigated,
                "fresh": ob_r.fresh,
            }] if ob_r and ob_r.ob_detected else [],
            "fvg": [{
                "type": fvg_r.fvg_type,
                "top": fvg_r.fvg_top,
                "bottom": fvg_r.fvg_bottom,
                "size": fvg_r.fvg_size,
                "mitigated": fvg_r.mitigated,
            }] if fvg_r and fvg_r.fvg_detected else [],
            "imbalance": {},
            "premium_discount": {
                "zone": pd_r.zone if pd_r else None,
                "equilibrium": pd_r.equilibrium if pd_r else None,
                "premium_high": pd_r.premium_high if pd_r else None,
                "discount_low": pd_r.discount_low if pd_r else None,
                "price_position": pd_r.price_position if pd_r else None,
            } if pd_r else {},
            "scoring": {
                "direction": self.direction,
                "score": self.score,
                "rank": self.rank,
                "confidence_score": self.confidence_score,
                "confidence_label": self.confidence_label,
                "approved": self.approved,
                "recommendation": sc_r.recommendation if sc_r else None,
                "breakdown": sc_r.breakdown if sc_r else {},
                "reasons": list(self.reasons) if self.reasons else [],
            },
            "execution": exec_data,
            "trade": {},
            "chart": {
                "ohlc": (self.chart_data or {}).get("ohlc", []),
                "indicators": (self.chart_data or {}).get("indicators", {}),
            },
            "drawing": {
                "entry": {
                    "price": self.entry_zone.get("entry_price") if self.entry_zone else None,
                    "time": self._to_json_val(self.timestamp),
                } if self.entry_zone else None,
                "sl": self.stop_loss,
                "tp": [self.take_profit] if self.take_profit is not None else [],
                "buy_sell": self.direction,
                "rr": None,
                "be_price": None,
                "mfe_price": None,
                "mae_price": None,
            },
            "statistics": {},
            "session": {
                "label": sess.current_session.label if sess and sess.current_session else None,
                "session_type": self._to_json_val(sess.current_session.session_type) if sess and sess.current_session else None,
                "sessions_active": sess.sessions_active if sess else [],
                "is_kill_zone": sess.is_kill_zone if sess else False,
                "kill_zones_active": sess.kill_zones_active if sess else [],
                "asian_high": sess.asian_high if sess else None,
                "asian_low": sess.asian_low if sess else None,
                "pdh": sess.pdh if sess else None,
                "pdl": sess.pdl if sess else None,
            } if sess else {},
        }


class SetupDetector:
    def __init__(self):
        self.structure_detector = MarketStructureDetector()
        self.liquidity_engine = LiquidityEngine()
        self.fvg_detector = FVGDetector()
        self.vi_detector = VolumeImbalanceDetector()
        self.lv_detector = LiquidityVoidDetector()
        self.ob_engine = OrderBlockEngine()
        self.pd_detector = PremiumDiscountDetector()
        self.sr_detector = SupportResistanceDetector()
        self.candle_detector = CandlePatternDetector()
        self.score_engine = ScoreEngine()
        self.setup_ranker = SetupRanker()
        self.confidence_engine = ConfidenceScoreEngine()

        # Read by engine_runner after each detect() call
        self.last_detect_result: Optional[dict] = None
        self._per_symbol_results: dict[str, dict] = {}

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        return df.rename(columns=COLUMN_MAP)

    async def detect(self, market_data: MarketData, symbol: str,
                     timeframe: str = "M5", count: int = 500,
                     dt: Optional[datetime] = None) -> Optional[SetupCandidate]:
        df, session = await market_data.get_rates_with_session(symbol, timeframe, count, dt)
        if df.empty:
            logger.warning("Empty data for %s %s (count=%d)", symbol, timeframe, count)
            return None
        logger.info("Data fetched for %s %s: %d bars, last=%s", symbol, timeframe, len(df), df.index[-1] if hasattr(df, 'index') and len(df.index) > 0 else '?')
        return await asyncio.to_thread(self._pipeline, df, symbol, timeframe, session)

    def _pipeline(self, df: pd.DataFrame, symbol: str, timeframe: str,
                  session: Optional[SessionAnalysis] = None) -> Optional[SetupCandidate]:
        df = self._normalize_columns(df)

        # Step 1 — Market Structure
        df = self.structure_detector.process_structure(df)
        structure = self._extract_structure(df)
        if not structure.valid:
            direction = self._fallback_direction(df)
            if direction:
                logger.debug("Fallback direction for %s: %s", symbol, direction)
                structure.trend_direction = direction
            else:
                logger.info("No valid market structure for %s: no MSS/CHoCH/BOS and no fallback", symbol)
                return None

        # Step 2 — Liquidity
        df = self.liquidity_engine.process_liquidity(df)
        liquidity = self._extract_liquidity(df)

        # Step 3 — FVG
        df = self.fvg_detector.process_fvg(df)
        fvg = self._extract_fvg(df)

        # Step 4 — Volume Imbalance (placeholder)
        df = self.vi_detector.process_volume_imbalance(df)

        # Step 5 — Liquidity Void (placeholder)
        df = self.lv_detector.process_liquidity_void(df)

        # Step 6 — Order Blocks
        df = self.ob_engine.process_order_blocks(df)
        ob = self._extract_ob(df)

        # Step 7 — Premium / Discount
        df = self.pd_detector.process_premium_discount(df)
        premium_discount = self._extract_premium_discount(df)

        # Step 8 — Support / Resistance (placeholder)
        df = self.sr_detector.process_support_resistance(df)

        # Step 9 — Candle (placeholder)
        df = self.candle_detector.process_candle_patterns(df)

        # Step 10 — Score + Ranker + Confidence
        df = self.score_engine.process_score(df)
        df = self.setup_ranker.process_rankings(df)
        df = self.confidence_engine.process_confidence(df)
        score_result = self._extract_score(df)

        last = df.iloc[-1] if not df.empty else None
        trend_str = str(getattr(structure, 'trend', '?'))
        dir_str = str(getattr(structure, 'trend_direction', '?')) or '?'
        bos = getattr(structure, 'bos_detected', False)
        choch = getattr(structure, 'choch_detected', False)
        mss = getattr(structure, 'mss_detected', False)
        liq = getattr(liquidity, 'valid', False) and getattr(liquidity, 'sweep_detected', False)
        fvg_ok = getattr(fvg, 'valid', False)
        ob_ok = getattr(ob, 'valid', False)
        sess = str(getattr(session, 'session_type', '--')) if session else '--'
        displacement = bool(last.get('Displacement_Detected', False)) if last is not None else False
        candle = bool(last.get('Candle_Pattern_Detected', False)) if last is not None else False

        detail = (
            f"\n{'='*50}"
            f"\n{symbol} | {timeframe}"
            f"\nTrend: {trend_str} | Dir: {dir_str}"
            f"\n  BOS ............ {'PASS' if bos else '--'}"
            f"\n  CHoCH .......... {'PASS' if choch else '--'}"
            f"\n  MSS ............ {'PASS' if mss else '--'}"
            f"\n  Liquidity ...... {'PASS' if liq else '--'}"
            f"\n  FVG ............ {'PASS' if fvg_ok else '--'}"
            f"\n  Order Block .... {'PASS' if ob_ok else '--'}"
            f"\n  Displacement ... {'PASS' if displacement else '--'}"
            f"\n  Candle Pattern . {'PASS' if candle else '--'}"
            f"\n  Session ........ {sess}"
            f"\n{'-'*50}"
        )
        if score_result.breakdown:
            for k, v in score_result.breakdown.items():
                detail += f"\n  {k}: {v:.1f}"
        detail += f"\n{'─'*50}"
        detail += f"\nFinal Score = {score_result.score:.1f}  Required >= 60"
        detail += f"\nRecommendation = {score_result.recommendation}"
        detail += f"\n{'='*50}"

        result = {
            "rejected": score_result.recommendation == "REJECT",
            "score": score_result.score,
            "recommendation": score_result.recommendation,
            "structure_valid": getattr(structure, 'valid', False),
            "bos": bos, "choch": choch, "mss": mss,
            "liquidity": liq, "fvg": fvg_ok, "orderblock": ob_ok,
            "displacement": displacement, "candle": candle,
        }
        self.last_detect_result = result
        self._per_symbol_results[symbol] = result

        if score_result.recommendation == "REJECT":
            logger.info("Setup rejected for %s | score=%.1f%s", symbol, score_result.score, detail)
            return None
        logger.info("Setup accepted for %s | score=%.1f direction=%s%s", symbol, score_result.score, dir_str, detail)

        return self._extract_candidate(df, symbol, timeframe, session, structure, liquidity, fvg, ob, premium_discount, score_result)

    def _extract_liquidity(self, df: pd.DataFrame) -> LiquidityResult:
        if df.empty:
            return LiquidityResult(valid=False)
        last = df.iloc[-1]

        valid_sweep = bool(last.get("Valid_Sweep", False))
        liq_sweep = bool(last.get("Liquidity_Sweep", False))
        source = str(last.get("Liquidity_Source")) if pd.notna(last.get("Liquidity_Source")) else None
        sweep_type = str(last.get("Sweep_Type")) if pd.notna(last.get("Sweep_Type")) else None
        sweep_level = float(last["Sweep_Level"]) if pd.notna(last.get("Sweep_Level")) else None
        strength = float(last.get("Sweep_Strength", 0)) if pd.notna(last.get("Sweep_Strength")) else 0.0
        rank = float(last.get("Liquidity_Rank", 0)) if pd.notna(last.get("Liquidity_Rank")) else 0.0
        eqh = bool(last.get("EQH", False))
        eql = bool(last.get("EQL", False))

        pdl_swept = source == "PDL"
        pdh_swept = source == "PDH"
        asian_high_swept = source == "ASIAN_HIGH"
        asian_low_swept = source == "ASIAN_LOW"

        sweep_detected = valid_sweep or liq_sweep

        reasons = []
        if sweep_detected:
            reasons.append(f"Sweep_{source}")
        if eqh:
            reasons.append("EQH")
        if eql:
            reasons.append("EQL")

        return LiquidityResult(
            valid=sweep_detected or eqh or eql,
            sweep_detected=sweep_detected,
            sweep_type=sweep_type,
            sweep_price=sweep_level,
            sweep_strength=strength,
            liquidity_source=source,
            liquidity_rank=rank,
            equal_highs=eqh,
            equal_lows=eql,
            pdh_swept=pdh_swept,
            pdl_swept=pdl_swept,
            asian_high_swept=asian_high_swept,
            asian_low_swept=asian_low_swept,
            reasons=reasons,
        )

    def _extract_fvg(self, df: pd.DataFrame) -> FVGResult:
        if df.empty:
            return FVGResult(valid=False)
        last = df.iloc[-1]

        bullish = bool(last.get("Bullish_FVG", False))
        bearish = bool(last.get("Bearish_FVG", False))
        fvg_detected = bullish or bearish
        fvg_type = "BULLISH" if bullish else ("BEARISH" if bearish else None)
        mitigated = bool(last.get("FVG_Mitigated", False))

        fvg_top = float(last["FVG_Upper"]) if pd.notna(last.get("FVG_Upper")) else None
        fvg_bottom = float(last["FVG_Lower"]) if pd.notna(last.get("FVG_Lower")) else None
        fvg_size = float(last["FVG_Size"]) if pd.notna(last.get("FVG_Size")) else None

        reasons = []
        if bullish:
            reasons.append("Bullish_FVG")
        if bearish:
            reasons.append("Bearish_FVG")

        return FVGResult(
            valid=fvg_detected and not mitigated,
            fvg_detected=fvg_detected,
            fvg_type=fvg_type,
            fvg_top=fvg_top,
            fvg_bottom=fvg_bottom,
            fvg_size=fvg_size,
            mitigated=mitigated,
            reasons=reasons,
        )

    def _extract_ob(self, df: pd.DataFrame) -> OrderBlockResult:
        if df.empty:
            return OrderBlockResult(valid=False)
        last = df.iloc[-1]

        bullish = bool(last.get("Bullish_OB", False))
        bearish = bool(last.get("Bearish_OB", False))
        ob_detected = bullish or bearish
        ob_type = "BULLISH" if bullish else ("BEARISH" if bearish else None)
        mitigated = bool(last.get("OB_Mitigated", False))

        top = float(last["OB_Upper"]) if pd.notna(last.get("OB_Upper")) else None
        bottom = float(last["OB_Lower"]) if pd.notna(last.get("OB_Lower")) else None
        ob_mid = (float(top) + float(bottom)) / 2 if top is not None and bottom is not None else None

        reasons = []
        if bullish:
            reasons.append("Bullish_OB")
        if bearish:
            reasons.append("Bearish_OB")

        return OrderBlockResult(
            valid=ob_detected and not mitigated,
            ob_detected=ob_detected,
            ob_type=ob_type,
            ob_top=top,
            ob_bottom=bottom,
            ob_mid=ob_mid,
            mitigated=mitigated,
            fresh=int(last.get("OB_Touches", 0)) == 0,
            reasons=reasons,
        )

    def _extract_premium_discount(self, df: pd.DataFrame) -> PremiumDiscountResult:
        if df.empty:
            return PremiumDiscountResult(valid=False)
        last = df.iloc[-1]

        zone = last.get("PD_Zone") or last.get("Premium_Discount_Zone")
        equilibrium = float(last["Equilibrium"]) if pd.notna(last.get("Equilibrium")) else None
        premium_high = float(last["Premium_High"]) if pd.notna(last.get("Premium_High")) else None
        discount_low = float(last["Discount_Low"]) if pd.notna(last.get("Discount_Low")) else None
        price_position = float(last["Price_Position"]) if pd.notna(last.get("Price_Position")) else None

        reasons = []
        if zone:
            reasons.append(f"PD_{zone}")

        return PremiumDiscountResult(
            valid=zone is not None,
            zone=zone,
            equilibrium=equilibrium,
            premium_high=premium_high,
            discount_low=discount_low,
            price_position=price_position,
            reasons=reasons,
        )

    def _extract_score(self, df: pd.DataFrame) -> ScoreResult:
        if df.empty:
            return ScoreResult(valid=False, score=0, confidence=0, rank="IGNORE", recommendation="REJECT")
        last = df.iloc[-1]

        score_val = float(last.get("Setup_Final_Score", last.get("Setup_Score", 0)))
        confidence = float(last.get("Confidence_Score", 0))
        rank = str(last.get("Setup_Rank", "IGNORE"))

        if score_val >= 90:
            recommendation = "EXECUTE"
        elif score_val >= 75:
            recommendation = "WATCHLIST"
        elif score_val >= 60:
            recommendation = "WAIT"
        else:
            recommendation = "REJECT"

        breakdown = {}
        for key in ("Structure_Confidence", "Liquidity_Confidence",
                     "Imbalance_Confidence", "Direction_Alignment",
                     "Confidence_Penalty", "Setup_Score", "Candidate_Priority_Score"):
            val = last.get(key)
            if val is not None and pd.notna(val):
                breakdown[key] = float(val)

        reasons = []
        if recommendation == "EXECUTE":
            reasons.append("RECOMMEND_EXECUTE")
        elif recommendation == "WATCHLIST":
            reasons.append("RECOMMEND_WATCHLIST")
        elif recommendation == "WAIT":
            reasons.append("RECOMMEND_WAIT")

        valid = bool(last.get("Setup_Approved", False)) and recommendation != "REJECT"

        return ScoreResult(
            valid=valid,
            score=score_val,
            confidence=confidence,
            rank=rank,
            recommendation=recommendation,
            breakdown=breakdown,
            reasons=reasons,
        )

    def _extract_structure(self, df: pd.DataFrame, lookback: int = 50) -> MarketStructureResult:
        if df.empty:
            return MarketStructureResult(valid=False, trend="NEUTRAL", trend_direction=None)

        last = df.iloc[-1]
        trend = str(last.get("Market_Trend", "NEUTRAL"))
        tail = df.tail(lookback)
        mss = bool(tail["MSS"].any()) if "MSS" in tail.columns else False
        choch = bool(tail["CHoCH"].any()) if "CHoCH" in tail.columns else False
        bos = bool(tail["BOS"].any()) if "BOS" in tail.columns else False

        if "BULLISH" in trend:
            trend_dir = "BUY"
        elif "BEARISH" in trend:
            trend_dir = "SELL"
        else:
            trend_dir = self._structure_direction(last)

        valid = mss or choch or bos

        return MarketStructureResult(
            valid=valid,
            trend=trend,
            trend_direction=trend_dir,
            bos_detected=bos,
            choch_detected=choch,
            mss_detected=mss,
            bos_type=str(last.get("BOS_Type")) if pd.notna(last.get("BOS_Type")) else None,
            choch_type=str(last.get("CHoCH_Type")) if pd.notna(last.get("CHoCH_Type")) else None,
            mss_type=str(last.get("MSS_Type")) if pd.notna(last.get("MSS_Type")) else None,
            structure_id=str(last.get("Structure_ID")) if pd.notna(last.get("Structure_ID")) else None,
            protected_high=float(last["Protected_High_Level"]) if pd.notna(last.get("Protected_High_Level")) else None,
            protected_low=float(last["Protected_Low_Level"]) if pd.notna(last.get("Protected_Low_Level")) else None,
            sweep_detected=False,
            sweep_price=None,
            sweep_type=None,
            consecutive_bos=int(last.get("BOS_Count", 0)) if "BOS_Count" in df.columns else None,
            strong_high=float(last["Strong_High"]) if pd.notna(last.get("Strong_High")) else None,
            strong_low=float(last["Strong_Low"]) if pd.notna(last.get("Strong_Low")) else None,
            weak_high=float(last["Weak_High"]) if pd.notna(last.get("Weak_High")) else None,
            weak_low=float(last["Weak_Low"]) if pd.notna(last.get("Weak_Low")) else None,
        )

    def _structure_direction(self, row) -> Optional[str]:
        mss_t = str(row.get("MSS_Type", ""))
        choch_t = str(row.get("CHoCH_Type", ""))
        bos_t = str(row.get("BOS_Type", ""))
        if "Bullish" in mss_t or "Bullish" in choch_t or "Bullish" in bos_t:
            return "BUY"
        if "Bearish" in mss_t or "Bearish" in choch_t or "Bearish" in bos_t:
            return "SELL"
        return None

    def _fallback_direction(self, df: pd.DataFrame) -> Optional[str]:
        if df.empty:
            return None
        last = df.iloc[-1]
        trend = str(last.get("Market_Trend", "NEUTRAL"))
        if "BULLISH" in trend:
            return "BUY"
        if "BEARISH" in trend:
            return "SELL"
        return self._structure_direction(last)

    def _extract_candidate(self, df: pd.DataFrame, symbol: str, timeframe: str,
                           session: Optional[SessionAnalysis],
                           structure: MarketStructureResult,
                           liquidity: Optional[LiquidityResult] = None,
                           fvg: Optional[FVGResult] = None,
                           ob: Optional[OrderBlockResult] = None,
                           premium_discount: Optional[PremiumDiscountResult] = None,
                           score_result: Optional[ScoreResult] = None) -> Optional[SetupCandidate]:
        if df.empty:
            return None

        direction = structure.trend_direction
        if direction is None:
            return None

        last = df.iloc[-1]
        reasons = self._collect_reasons(last, structure, liquidity, fvg, ob, premium_discount, score_result)

        # Capture last ~80 OHLC candles for chart snapshot + indicators
        ohlc_window = 80
        vol_col = "TickVolume" if "TickVolume" in df.columns else "Volume" if "Volume" in df.columns else None
        ohlc_cols = ["Open", "High", "Low", "Close"]
        if vol_col:
            ohlc_cols = ohlc_cols + [vol_col]
        ohlc_slice = df[ohlc_cols].tail(ohlc_window).copy()
        ohlc_data = []
        closes = []
        highs = []
        lows = []
        for ts, row in ohlc_slice.iterrows():
            c = float(row["Close"])
            candle = {
                "time": int(ts.timestamp()),
                "open": round(float(row["Open"]), 5),
                "high": round(float(row["High"]), 5),
                "low": round(float(row["Low"]), 5),
                "close": round(c, 5),
            }
            if vol_col and vol_col in row:
                candle["volume"] = int(float(row[vol_col]))
            ohlc_data.append(candle)
            closes.append(c)
            highs.append(float(row["High"]))
            lows.append(float(row["Low"]))

        # Indicators
        indicator_data = {}
        if len(closes) >= 14:
            tr_vals = []
            for i in range(1, len(ohlc_data)):
                hl = highs[i] - lows[i]
                hc = abs(highs[i] - closes[i-1])
                lc = abs(lows[i] - closes[i-1])
                tr_vals.append(max(hl, hc, lc))
            atr_vals = []
            for i in range(len(tr_vals)):
                if i < 13:
                    atr_vals.append(sum(tr_vals[:i+1]) / (i+1))
                else:
                    atr_vals.append((atr_vals[-1] * 13 + tr_vals[i]) / 14)
            indicator_data["atr"] = [
                {"time": ohlc_data[i+1]["time"], "value": round(v, 5)}
                for i, v in enumerate(atr_vals)
            ]

        if len(closes) >= 20:
            ema20 = []
            alpha = 2 / (20 + 1)
            sma = sum(closes[:20]) / 20
            for i, c in enumerate(closes):
                if i < 19:
                    ema20.append(round(sma, 5))
                elif i == 19:
                    ema20.append(round(sma, 5))
                else:
                    val = (c - ema20[-1]) * alpha + ema20[-1]
                    ema20.append(round(val, 5))
            indicator_data["ema20"] = [
                {"time": ohlc_data[i]["time"], "value": v}
                for i, v in enumerate(ema20)
            ]

        if len(closes) >= 50:
            ema50 = []
            alpha = 2 / (50 + 1)
            sma = sum(closes[:50]) / 50
            for i, c in enumerate(closes):
                if i < 49:
                    ema50.append(round(sma, 5))
                elif i == 49:
                    ema50.append(round(sma, 5))
                else:
                    val = (c - ema50[-1]) * alpha + ema50[-1]
                    ema50.append(round(val, 5))
            indicator_data["ema50"] = [
                {"time": ohlc_data[i]["time"], "value": v}
                for i, v in enumerate(ema50)
            ]

        chart_data = {
            "ohlc": ohlc_data,
            "indicators": indicator_data,
        }

        return SetupCandidate(
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            structure=structure,
            liquidity=liquidity,
            fvg=fvg,
            ob=ob,
            premium_discount=premium_discount,
            score_result=score_result,
            score=score_result.score if score_result else 0,
            rank=score_result.rank if score_result else "IGNORE",
            confidence_score=score_result.confidence if score_result else 0,
            confidence_label=str(last.get("Confidence_Label", "NO_TRADE")),
            approved=bool(last.get("Setup_Approved", False)),
            reasons=reasons,
            setup_id=last.get("Setup_ID"),
            reject_reason=last.get("Setup_Reject_Reason"),
            timestamp=df.index[-1] if isinstance(df.index[-1], datetime) else None,
            session=session,
            chart_data=chart_data,
        )

    def _collect_reasons(self, row, structure: MarketStructureResult,
                          liquidity: Optional[LiquidityResult] = None,
                          fvg: Optional[FVGResult] = None,
                          ob: Optional[OrderBlockResult] = None,
                          premium_discount: Optional[PremiumDiscountResult] = None,
                          score_result: Optional[ScoreResult] = None) -> List[str]:
        reasons = []
        if structure.mss_detected:
            reasons.append("MSS")
        if structure.choch_detected:
            reasons.append("CHoCH")
        if structure.bos_detected:
            reasons.append("BOS")
        if liquidity and liquidity.sweep_detected:
            reasons.extend(liquidity.reasons)
            if liquidity.pdh_swept:
                reasons.append("PDH_Swept")
            if liquidity.pdl_swept:
                reasons.append("PDL_Swept")
            if liquidity.asian_high_swept:
                reasons.append("Asian_High_Swept")
            if liquidity.asian_low_swept:
                reasons.append("Asian_Low_Swept")
        if fvg and fvg.fvg_detected:
            reasons.extend(fvg.reasons)
        if ob and ob.ob_detected:
            reasons.extend(ob.reasons)
        if premium_discount and premium_discount.valid:
            reasons.extend(premium_discount.reasons)
        if score_result and score_result.valid:
            reasons.extend(score_result.reasons)
        for col in ("Candle_Valid_Buy", "Candle_Valid_Sell"):
            if bool(row.get(col, False)):
                reasons.append(col)
        return reasons

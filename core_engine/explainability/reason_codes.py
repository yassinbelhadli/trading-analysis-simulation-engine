"""Canonical reason codes — shared by engine, formatter, renderer, and downstream.

Each code uses UPPER_SNAKE convention. Display text lives in formatter/translator.
"""

from enum import Enum


class ReasonCode(Enum):
    # ── Structure ──
    BOS_BULLISH = "BOS_BULLISH"
    BOS_BEARISH = "BOS_BEARISH"
    CHOCH_BULLISH = "CHOCH_BULLISH"
    CHOCH_BEARISH = "CHOCH_BEARISH"
    MSS_BULLISH = "MSS_BULLISH"
    MSS_BEARISH = "MSS_BEARISH"

    # ── Liquidity ──
    SSL_SWEEP = "SSL_SWEEP"       # Sell-side liquidity sweep
    BSL_SWEEP = "BSL_SWEEP"       # Buy-side liquidity sweep
    PDH_BREAKOUT = "PDH_BREAKOUT"
    PDL_BREAKOUT = "PDL_BREAKOUT"

    # ── Order Blocks ──
    FRESH_OB = "FRESH_OB"
    OB_MITIGATED = "OB_MITIGATED"
    OB_RESPECTED = "OB_RESPECTED"

    # ── FVG ──
    FVG_PRESENT = "FVG_PRESENT"
    FVG_MITIGATED = "FVG_MITIGATED"
    FVG_RESPECTED = "FVG_RESPECTED"

    # ── Confirmation ──
    PRICE_AT_ZONE = "PRICE_AT_ZONE"
    RETEST_CONFIRMED = "RETEST_CONFIRMED"
    PROXIMITY_OK = "PROXIMITY_OK"

    # ── Risk ──
    RR_FAVORABLE = "RR_FAVORABLE"
    STOP_TIGHT = "STOP_TIGHT"
    RISK_LIMIT_OK = "RISK_LIMIT_OK"

    # ── Scoring ──
    SCORE_HIGH = "SCORE_HIGH"
    SCORE_MEDIUM = "SCORE_MEDIUM"
    SCORE_LOW = "SCORE_LOW"

    # ── News / filters ──
    NO_HIGH_IMPACT_NEWS = "NO_HIGH_IMPACT_NEWS"

    # ── Invalidation ──
    INVALID_NEW_MSS = "INVALID_NEW_MSS"
    INVALID_OB_BREACH = "INVALID_OB_BREACH"
    INVALID_FVG_FILL = "INVALID_FVG_FILL"
    INVALID_ZONE_AGE = "INVALID_ZONE_AGE"
    INVALID_PRICE_FAR = "INVALID_PRICE_FAR"

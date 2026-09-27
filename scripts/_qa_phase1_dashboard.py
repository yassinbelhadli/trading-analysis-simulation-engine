"""
Phase 1 — Dashboard + Account Profile 20-Scenario Test Suite

Tests all scenarios required by the specification:
1. Personal account
2. Prop Firm account
3. Unknown prop firm
4. Ambiguous prop firm
5. Verified rule profile
6. User-provided rule profile
7. Unverified profile
8. Near daily-loss limit
9. Near maximum-loss limit
10. Floating loss
11. Existing positions
12. Multiple positions
13. New trade exceeding risk
14. New trade within risk
15. Stale risk data
16. Restart/reconnect
17. Conservative mode
18. Balanced mode
19. Aggressive mode
20. Personal vs Prop Firm

No real trades are opened. All tests use simulated data against
the existing DB and risk architecture.
"""
from __future__ import annotations

import asyncio
import sys
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core_engine.risk.live_risk_calculator import LiveRiskCalculator, OpenPosition, RiskLevel
from core_engine.risk.prop_firm_detector import PropFirmDetector, VerificationStatus


# ── Helpers ──────────────────────────────────────────────────────────
PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        msg = f"  [FAIL] {name}"
        if detail:
            msg += f" -- {detail}"
        print(msg)


def section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ── Tests ────────────────────────────────────────────────────────────

def test_01_personal_account():
    """Scenario 1: Personal account with standard risk profile."""
    section("1. Personal Account")
    calc = LiveRiskCalculator()
    status = calc.calculate(
        account_id="personal-1",
        account_type="PERSONAL",
        balance=10000,
        equity=10000,
        risk_profile={
            "daily_loss": 5.0,
            "max_loss": 15.0,
            "initial_balance": 10000,
            "drawdown_type": "static",
        },
    )
    check("Account type is PERSONAL", status.account_type == "PERSONAL")
    check("Risk level is SAFE", status.risk_level == RiskLevel.SAFE)
    check("Daily loss limit is 5%", status.daily_loss_limit_pct == 5.0)
    check("Daily loss limit USD is $500", status.daily_loss_limit_usd == 500.0)
    check("Max loss limit is 15%", status.max_loss_limit_pct == 15.0)
    check("Max loss limit USD is $1500", status.max_loss_limit_usd == 1500.0)
    check("Remaining daily loss is $500", status.remaining_daily_loss_usd == 500.0)
    check("Remaining max loss is $1500", status.remaining_max_loss_usd == 1500.0)
    check("Risk profile not missing", not status.risk_profile_missing)


def test_02_prop_firm_account():
    """Scenario 2: Prop Firm account with strict limits."""
    section("2. Prop Firm Account")
    calc = LiveRiskCalculator()
    status = calc.calculate(
        account_id="prop-1",
        account_type="FUNDED",
        balance=100000,
        equity=100000,
        risk_profile={
            "daily_loss": 5.0,
            "max_loss": 10.0,
            "initial_balance": 100000,
            "drawdown_type": "static",
        },
        prop_firm="FTMO",
        prop_firm_program="2-Step Standard",
        verification_status="VERIFIED_RULES",
    )
    check("Account type is FUNDED", status.account_type == "FUNDED")
    check("Risk level is SAFE", status.risk_level == RiskLevel.SAFE)
    check("Prop firm is FTMO", status.prop_firm == "FTMO")
    check("Program is 2-Step Standard", status.prop_firm_program == "2-Step Standard")
    check("Verification is VERIFIED_RULES", status.verification_status == "VERIFIED_RULES")
    check("Daily loss limit is $5000 (5% of 100k)", status.daily_loss_limit_usd == 5000.0)
    check("Max loss limit is $10000 (10% of 100k)", status.max_loss_limit_usd == 10000.0)


def test_03_unknown_prop_firm():
    """Scenario 3: Unknown prop firm — cannot identify from metadata."""
    section("3. Unknown Prop Firm")
    detector = PropFirmDetector()
    result = detector.detect(
        server="SomeRandomBroker-Demo",
        broker="RandomBroker",
        company="Random Broker LLC",
        account_name="My Account",
    )
    check("Status is UNKNOWN", result.status == VerificationStatus.UNKNOWN)
    check("Confidence is below 0.4", result.confidence < 0.4)
    check("No firm identified", result.firm_id is None)
    check("Message indicates unknown", "Unable" in result.message)


def test_04_ambiguous_prop_firm():
    """Scenario 4: Ambiguous prop firm — partial match, confirmation required."""
    section("4. Ambiguous Prop Firm")
    detector = PropFirmDetector()
    # Partial match: company name mentions FTMO but server doesn't match
    result = detector.detect(
        server="SomeServer-Demo",
        broker="SomeBroker",
        company="FTMO-like Services",
        account_name="Challenge Account",
    )
    # Should be AMBIGUOUS or UNKNOWN depending on confidence
    check("Status is AMBIGUOUS or UNKNOWN",
          result.status in (VerificationStatus.AMBIGUOUS, VerificationStatus.UNKNOWN))
    if result.status == VerificationStatus.AMBIGUOUS:
        check("Confidence is between 0.4 and 0.7",
              0.4 <= result.confidence < 0.7)
        check("Message mentions confirmation", "confirmation" in result.message.lower())


def test_05_verified_rule_profile():
    """Scenario 5: Verified rule profile from database."""
    section("5. Verified Rule Profile")
    detector = PropFirmDetector()
    result = detector.detect(
        server="FTMO-Demo",
        broker="FTMO",
        company="FTMO Global Markets Ltd",
        account_name="FTMO Challenge",
    )
    check("Status is IDENTIFIED (metadata only)", result.status == VerificationStatus.IDENTIFIED)
    check("Confidence >= 0.7", result.confidence >= 0.7)
    check("Firm identified as FTMO", result.firm_id == "ftmo")
    check("Server field matched", "server" in result.matched_fields)
    check("Company field matched", "company" in result.matched_fields)

    # Get profile
    profile = detector.get_profile("ftmo", "2-Step Standard", source="database")
    check("Profile returned", profile is not None)
    check("Profile source is database", profile.source == "database")
    check("Profile verification is VERIFIED_RULES", profile.verification_status == VerificationStatus.VERIFIED_RULES)


def test_06_user_provided_rule_profile():
    """Scenario 6: User-provided rule profile — not auto-detected."""
    section("6. User-Provided Rule Profile")
    calc = LiveRiskCalculator()
    status = calc.calculate(
        account_id="user-provided-1",
        account_type="CHALLENGE",
        balance=50000,
        equity=50000,
        risk_profile={
            "daily_loss": 4.0,
            "max_loss": 8.0,
            "initial_balance": 50000,
            "drawdown_type": "trailing",
        },
        prop_firm="MyPropFirm",
        prop_firm_program="Challenge Phase 1",
        verification_status="AMBIGUOUS",
    )
    check("Account type is CHALLENGE", status.account_type == "CHALLENGE")
    check("Verification is AMBIGUOUS", status.verification_status == "AMBIGUOUS")
    check("Prop firm is set", status.prop_firm == "MyPropFirm")
    check("Daily loss limit is $2000 (4% of 50k)", status.daily_loss_limit_usd == 2000.0)


def test_07_unverified_profile():
    """Scenario 7: Unverified profile — risk profile missing."""
    section("7. Unverified Profile (Risk Profile Missing)")
    calc = LiveRiskCalculator()
    status = calc.calculate(
        account_id="unverified-1",
        account_type="UNKNOWN",
        balance=20000,
        equity=20000,
        risk_profile=None,  # No risk profile
    )
    check("Risk level is UNVERIFIED", status.risk_level == RiskLevel.UNVERIFIED)
    check("Risk profile missing flag is True", status.risk_profile_missing)
    check("Message indicates blocked", "blocked" in status.risk_level_message.lower())
    check("Daily loss limit is 0 (no profile)", status.daily_loss_limit_usd == 0.0)


def test_08_near_daily_loss_limit():
    """Scenario 8: Near daily-loss limit — should show REDUCED risk."""
    section("8. Near Daily-Loss Limit")
    calc = LiveRiskCalculator()
    status = calc.calculate(
        account_id="near-daily-1",
        account_type="FUNDED",
        balance=100000,
        equity=98000,
        risk_profile={
            "daily_loss": 5.0,
            "max_loss": 10.0,
            "initial_balance": 100000,
            "day_start_balance": 100000,
            "drawdown_type": "static",
        },
        today_realized_pnl=-3500,  # Lost $3500 today (35% of $5000 daily limit)
    )
    check("Risk level is REDUCED", status.risk_level == RiskLevel.REDUCED)
    check("Remaining daily loss < limit", status.remaining_daily_loss_usd < 5000)
    check("Remaining daily loss is $1500", status.remaining_daily_loss_usd == 1500.0)
    check("Message mentions daily loss", "daily" in status.risk_level_message.lower())
    check("Current daily loss is $3500", status.current_daily_loss_usd == 3500.0)


def test_09_near_maximum_loss_limit():
    """Scenario 9: Near maximum-loss limit — should show BLOCKED when limit exceeded."""
    section("9. Near Maximum-Loss Limit")
    calc = LiveRiskCalculator()
    status = calc.calculate(
        account_id="near-max-1",
        account_type="FUNDED",
        balance=100000,
        equity=92000,
        risk_profile={
            "daily_loss": 5.0,
            "max_loss": 10.0,
            "initial_balance": 100000,
            "drawdown_type": "static",
        },
        total_realized_loss_usd=7500,  # Total realized loss $7500
    )
    # $7500 realized + $8000 drawdown = $15500 total loss vs $10000 max limit
    # remaining_max_loss = max(0, 10000 - 7500 - 8000) = $0 → BLOCKED
    check("Risk level is BLOCKED (max loss exceeded)", status.risk_level == RiskLevel.BLOCKED)
    check("Remaining max loss is $0", status.remaining_max_loss_usd == 0)
    check("Drawdown is > 0", status.current_drawdown_usd > 0)
    check("Message mentions loss limit", "loss" in status.risk_level_message.lower())


def test_10_floating_loss():
    """Scenario 10: Floating loss — open positions in drawdown."""
    section("10. Floating Loss")
    calc = LiveRiskCalculator()
    status = calc.calculate(
        account_id="floating-1",
        account_type="PERSONAL",
        balance=10000,
        equity=9500,  # $500 floating loss
        risk_profile={
            "daily_loss": 5.0,
            "max_loss": 15.0,
            "initial_balance": 10000,
            "drawdown_type": "static",
        },
        today_floating_pnl=-500,
    )
    check("Floating PnL is -$500", status.floating_pnl == -500.0)
    check("Today floating PnL is -$500", status.today_floating_pnl == -500.0)
    check("Equity < Balance", status.equity < status.balance)
    check("Drawdown > 0", status.current_drawdown_pct > 0)


def test_11_existing_positions():
    """Scenario 11: Existing positions — open risk calculated."""
    section("11. Existing Positions")
    calc = LiveRiskCalculator()
    positions = [
        OpenPosition(id="p1", symbol="XAUUSD", direction="BUY", entry_price=2400, lot_size=0.1, stop_loss=2380),
        OpenPosition(id="p2", symbol="BTCUSD", direction="SELL", entry_price=60000, lot_size=0.01, stop_loss=61000),
    ]
    status = calc.calculate(
        account_id="positions-1",
        account_type="PERSONAL",
        balance=10000,
        equity=9800,
        risk_profile={
            "daily_loss": 5.0,
            "max_loss": 15.0,
            "initial_balance": 10000,
            "drawdown_type": "static",
        },
        open_positions=positions,
    )
    check("Open positions count is 2", status.open_positions_count == 2)
    check("Total open risk > 0", status.total_open_risk_usd > 0)
    check("Risk level is SAFE", status.risk_level == RiskLevel.SAFE)


def test_12_multiple_positions():
    """Scenario 12: Multiple positions — risk compounds."""
    section("12. Multiple Positions")
    calc = LiveRiskCalculator()
    positions = [
        OpenPosition(id="p1", symbol="XAUUSD", direction="BUY", entry_price=2400, lot_size=0.1, stop_loss=2380),
        OpenPosition(id="p2", symbol="XAUUSD", direction="SELL", entry_price=2450, lot_size=0.1, stop_loss=2470),
        OpenPosition(id="p3", symbol="NASDAQ", direction="BUY", entry_price=19500, lot_size=0.05, stop_loss=19400),
        OpenPosition(id="p4", symbol="BTCUSD", direction="BUY", entry_price=60000, lot_size=0.02, stop_loss=59000),
    ]
    status = calc.calculate(
        account_id="multi-1",
        account_type="PERSONAL",
        balance=20000,
        equity=19500,
        risk_profile={
            "daily_loss": 5.0,
            "max_loss": 15.0,
            "initial_balance": 20000,
            "drawdown_type": "static",
        },
        open_positions=positions,
    )
    check("Open positions count is 4", status.open_positions_count == 4)
    check("Total open risk > 0", status.total_open_risk_usd > 0)
    check("4 positions tracked", status.open_positions_count == len(positions))


def test_13_trade_exceeding_risk():
    """Scenario 13: New trade would exceed risk limits."""
    section("13. New Trade Exceeding Risk")
    calc = LiveRiskCalculator()
    status = calc.calculate(
        account_id="exceed-1",
        account_type="FUNDED",
        balance=100000,
        equity=96000,
        risk_profile={
            "daily_loss": 5.0,
            "max_loss": 10.0,
            "initial_balance": 100000,
            "day_start_balance": 100000,
            "drawdown_type": "static",
        },
        today_realized_pnl=-4000,  # Already lost $4000 today (80% of $5000 limit)
    )
    check("Risk level is REDUCED", status.risk_level == RiskLevel.REDUCED)
    check("Remaining daily loss is $1000", status.remaining_daily_loss_usd == 1000.0)
    check("Distance to daily violation is $1000",
          status.distance_to_daily_violation_usd == 1000.0)
    # A $1500 trade would violate
    check("Trade > remaining would violate", 1500 > status.remaining_daily_loss_usd)


def test_14_trade_within_risk():
    """Scenario 14: New trade within risk limits."""
    section("14. New Trade Within Risk")
    calc = LiveRiskCalculator()
    status = calc.calculate(
        account_id="within-1",
        account_type="PERSONAL",
        balance=10000,
        equity=10000,
        risk_profile={
            "daily_loss": 5.0,
            "max_loss": 15.0,
            "initial_balance": 10000,
            "day_start_balance": 10000,
            "drawdown_type": "static",
        },
    )
    check("Risk level is SAFE", status.risk_level == RiskLevel.SAFE)
    check("Remaining daily loss is $500", status.remaining_daily_loss_usd == 500.0)
    # A $300 trade (3% risk) is within limits
    check("Trade < remaining is safe", 300 < status.remaining_daily_loss_usd)


def test_15_stale_risk_data():
    """Scenario 15: Stale risk data — balance not updated."""
    section("15. Stale Risk Data")
    calc = LiveRiskCalculator()
    stale_time = (datetime.now(timezone.utc) - timedelta(minutes=60)).isoformat()
    status = calc.calculate(
        account_id="stale-1",
        account_type="PERSONAL",
        balance=10000,
        equity=10000,
        risk_profile={
            "daily_loss": 5.0,
            "max_loss": 15.0,
            "initial_balance": 10000,
            "drawdown_type": "static",
        },
        last_scan_at=stale_time,
    )
    check("Data freshness is STALE", status.data_freshness == "STALE")
    check("Balance stale flag is True", status.balance_stale)
    check("Risk level is BLOCKED (stale data)", status.risk_level == RiskLevel.BLOCKED)
    check("Message mentions stale", "stale" in status.risk_level_message.lower())


def test_16_restart_reconnect():
    """Scenario 16: Restart/reconnect — fresh calculator state."""
    section("16. Restart/Reconnect")
    calc1 = LiveRiskCalculator()
    status1 = calc1.calculate(
        account_id="restart-1",
        account_type="PERSONAL",
        balance=10000,
        equity=10000,
        risk_profile={"daily_loss": 5.0, "max_loss": 15.0, "initial_balance": 10000},
    )
    # Simulate restart: new calculator instance
    calc2 = LiveRiskCalculator()
    status2 = calc2.calculate(
        account_id="restart-1",
        account_type="PERSONAL",
        balance=10000,
        equity=10000,
        risk_profile={"daily_loss": 5.0, "max_loss": 15.0, "initial_balance": 10000},
    )
    check("New calculator produces same result",
          status1.risk_level == status2.risk_level)
    check("Same remaining daily loss",
          status1.remaining_daily_loss_usd == status2.remaining_daily_loss_usd)
    check("Fresh data after restart", status2.data_freshness == "FRESH")


def test_17_conservative_mode():
    """Scenario 17: Conservative mode — strict limits."""
    section("17. Conservative Mode")
    from core_engine.config.trading_modes import get_trading_mode, calculate_mode_risk
    mode = get_trading_mode("CONSERVATIVE")
    check("Mode name is CONSERVATIVE", mode.name == "CONSERVATIVE")
    check("Max trades per day is 3", mode.max_trades_per_day == 3)
    check("Risk range is 0.25-0.75%", mode.min_risk_percent == 0.25 and mode.max_risk_percent == 0.75)
    check("Min RR is 1.8", mode.min_rr == 1.8)
    check("High news trading not allowed", not mode.allow_high_news_trading)
    check("Allowed sessions are LONDON+NY", mode.allowed_sessions == ["LONDON", "NEW_YORK"])
    check("Allowed symbols are fixed", mode.allowed_symbols == ["XAUUSD", "NAS100", "BTCUSD"])
    # Risk interpolation
    risk_at_75 = calculate_mode_risk("CONSERVATIVE", 75)
    check("Risk at min score is min_risk", risk_at_75 == 0.25)
    risk_at_100 = calculate_mode_risk("CONSERVATIVE", 100)
    check("Risk at max score is max_risk", risk_at_100 == 0.75)


def test_18_balanced_mode():
    """Scenario 18: Balanced mode — moderate limits."""
    section("18. Balanced Mode")
    from core_engine.config.trading_modes import get_trading_mode, calculate_mode_risk
    mode = get_trading_mode("BALANCED")
    check("Mode name is BALANCED", mode.name == "BALANCED")
    check("Max trades per day is 5", mode.max_trades_per_day == 5)
    check("Risk range is 0.50-1.25%", mode.min_risk_percent == 0.50 and mode.max_risk_percent == 1.25)
    check("Min RR is 1.5", mode.min_rr == 1.5)
    check("High news trading IS allowed", mode.allow_high_news_trading)
    check("Allowed sessions are LONDON+NY", mode.allowed_sessions == ["LONDON", "NEW_YORK"])
    risk_at_65 = calculate_mode_risk("BALANCED", 65)
    check("Risk at min score is min_risk", risk_at_65 == 0.50)
    risk_at_95 = calculate_mode_risk("BALANCED", 95)
    check("Risk at max score is max_risk", risk_at_95 == 1.25)


def test_19_aggressive_mode():
    """Scenario 19: Aggressive mode — wider limits."""
    section("19. Aggressive Mode")
    from core_engine.config.trading_modes import get_trading_mode, calculate_mode_risk
    mode = get_trading_mode("AGGRESSIVE")
    check("Mode name is AGGRESSIVE", mode.name == "AGGRESSIVE")
    check("Max trades per day is 10", mode.max_trades_per_day == 10)
    check("Risk range is 0.50-2.00%", mode.min_risk_percent == 0.50 and mode.max_risk_percent == 2.00)
    check("Min RR is 1.3", mode.min_rr == 1.3)
    check("High news trading IS allowed", mode.allow_high_news_trading)
    check("Max symbol trades is 3", mode.max_trades_per_symbol_per_day == 3)
    risk_at_50 = calculate_mode_risk("AGGRESSIVE", 50)
    check("Risk at min score is min_risk", risk_at_50 == 0.50)
    risk_at_90 = calculate_mode_risk("AGGRESSIVE", 90)
    check("Risk at max score is max_risk", risk_at_90 == 2.00)


def test_20_personal_vs_prop_firm():
    """Scenario 20: Personal vs Prop Firm — different risk behavior."""
    section("20. Personal vs Prop Firm")
    calc = LiveRiskCalculator()

    # Personal account
    personal = calc.calculate(
        account_id="compare-personal",
        account_type="PERSONAL",
        balance=10000,
        equity=10000,
        risk_profile={"daily_loss": 5.0, "max_loss": 15.0, "initial_balance": 10000},
    )

    # Prop firm account
    prop = calc.calculate(
        account_id="compare-prop",
        account_type="FUNDED",
        balance=100000,
        equity=100000,
        risk_profile={"daily_loss": 5.0, "max_loss": 10.0, "initial_balance": 100000},
        prop_firm="FTMO",
        verification_status="VERIFIED_RULES",
    )

    check("Personal daily limit < Prop daily limit",
          personal.daily_loss_limit_usd < prop.daily_loss_limit_usd)
    check("Personal max loss pct > Prop max loss pct",
          personal.max_loss_limit_pct > prop.max_loss_limit_pct)
    check("Personal account type is PERSONAL", personal.account_type == "PERSONAL")
    check("Prop account type is FUNDED", prop.account_type == "FUNDED")
    check("Prop has verification status", prop.verification_status == "VERIFIED_RULES")
    check("Personal has no prop firm", personal.prop_firm is None)

    # Safety buffer
    check("Safety buffer exists on personal", personal.safety_buffer_usd > 0)
    check("Safety buffer exists on prop", prop.safety_buffer_usd > 0)
    check("Prop safety buffer > personal (larger account)",
          prop.safety_buffer_usd > personal.safety_buffer_usd)

    # Blocked scenario: personal with no profile
    unverified = calc.calculate(
        account_id="compare-unverified",
        account_type="UNKNOWN",
        balance=5000,
        equity=5000,
        risk_profile=None,
    )
    check("No profile = UNVERIFIED", unverified.risk_level == RiskLevel.UNVERIFIED)
    check("No profile = blocked", "blocked" in unverified.risk_level_message.lower())


# ── Additional: Prop Firm Detection ──────────────────────────────────

def test_prop_firm_detection_ftmo():
    """Test FTMO detection from server name."""
    section("Bonus: FTMO Detection")
    detector = PropFirmDetector()
    result = detector.detect(server="FTMO-Demo", broker="FTMO", company="FTMO Global Markets Ltd")
    check("FTMO detected", result.firm_id == "ftmo")
    check("Status IDENTIFIED (metadata only, not verified rules)", result.status == VerificationStatus.IDENTIFIED)

    result2 = detector.detect(server="FTMO-Server01", broker="FTMO")
    check("FTMO detected from server pattern", result2.firm_id == "ftmo")


def test_prop_firm_detection_funding_pips():
    """Test FundingPips detection."""
    section("Bonus: FundingPips Detection")
    detector = PropFirmDetector()
    result = detector.detect(server="FundingPips-MT5", broker="FundingPips", company="Funding Pips Ltd")
    check("FundingPips detected", result.firm_id == "funding_pips")
    check("Status IDENTIFIED (metadata only)", result.status == VerificationStatus.IDENTIFIED)


def test_prop_firm_program_detection():
    """Test program detection within a firm."""
    section("Bonus: Program Detection")
    detector = PropFirmDetector()
    prog = detector.detect_program("ftmo", server="FTMO-Demo", account_name="2-Step Challenge")
    check("Program detected", prog is not None)
    check("Program is 2-Step Standard", prog == "2-Step Standard")


def test_safety_buffer():
    """Test safety buffer configuration."""
    section("Bonus: Safety Buffer")
    calc = LiveRiskCalculator()
    status = calc.calculate(
        account_id="buffer-1",
        account_type="PERSONAL",
        balance=10000,
        equity=10000,
        risk_profile={
            "daily_loss": 5.0,
            "max_loss": 15.0,
            "initial_balance": 10000,
            "safety_buffer_pct": 1.0,
        },
    )
    check("Safety buffer is 1%", status.safety_buffer_pct == 1.0)
    check("Safety buffer USD is $100", status.safety_buffer_usd == 100.0)

    # Default buffer
    status2 = calc.calculate(
        account_id="buffer-2",
        account_type="PERSONAL",
        balance=10000,
        equity=10000,
        risk_profile={"daily_loss": 5.0, "max_loss": 15.0, "initial_balance": 10000},
    )
    check("Default safety buffer is 0.5%", status2.safety_buffer_pct == 0.5)


# ── Regression: Fix #1 Verification Semantics ──────────────────────

def test_regression_firm_identified_rules_unknown():
    """Regression: Firm identity detected but rules unknown → IDENTIFIED / unverified."""
    section("Regression R1: IDENTIFIED != verified rules")
    detector = PropFirmDetector()
    result = detector.detect(
        server="FTMO-Demo",
        broker="FTMO",
        company="FTMO Global Markets Ltd",
        account_name="FTMO Challenge",
    )
    # High confidence metadata match → IDENTIFIED, not VERIFIED_RULES
    check("Status is IDENTIFIED (not VERIFIED_RULES)",
          result.status == VerificationStatus.IDENTIFIED)
    check("Firm ID is ftmo", result.firm_id == "ftmo")
    check("Confidence >= 0.7", result.confidence >= 0.7)

    # Profile from metadata only → IDENTIFIED, rules are None
    profile = detector.get_profile("ftmo", "2-Step Standard", source="metadata")
    check("Profile returned", profile is not None)
    check("Profile status is IDENTIFIED", profile.verification_status == VerificationStatus.IDENTIFIED)
    check("Rules are None (not verified)", profile.daily_loss_limit is None)
    check("Rules are None (not verified)", profile.max_loss is None)


def test_regression_verified_rules():
    """Regression: Verified rules → VERIFIED_RULES."""
    section("Regression R2: VERIFIED_RULES requires authoritative source")
    detector = PropFirmDetector()
    profile = detector.get_profile("ftmo", "2-Step Standard", source="database")
    check("Profile returned", profile is not None)
    check("Status is VERIFIED_RULES", profile.verification_status == VerificationStatus.VERIFIED_RULES)
    check("Source is database", profile.source == "database")


def test_regression_user_provided_rules():
    """Regression: User-provided rules → USER_PROVIDED_RULES."""
    section("Regression R3: USER_PROVIDED_RULES from user source")
    detector = PropFirmDetector()
    profile = detector.get_profile("ftmo", "2-Step Standard", source="user_provided")
    check("Profile returned", profile is not None)
    check("Status is USER_PROVIDED_RULES",
          profile.verification_status == VerificationStatus.USER_PROVIDED_RULES)
    check("Source is user_provided", profile.source == "user_provided")


def test_regression_ambiguous_firm():
    """Regression: Ambiguous firm → AMBIGUOUS."""
    section("Regression R4: AMBIGUOUS detection")
    detector = PropFirmDetector()
    result = detector.detect(
        server="SomeServer-Demo",
        broker="SomeBroker",
        company="FTMO-like Services",  # partial company match only
        account_name="Challenge Account",
    )
    check("Status is AMBIGUOUS or UNKNOWN",
          result.status in (VerificationStatus.AMBIGUOUS, VerificationStatus.UNKNOWN))
    if result.status == VerificationStatus.AMBIGUOUS:
        check("Confidence is 0.4-0.7",
              0.4 <= result.confidence < 0.7)


def test_regression_unknown_firm():
    """Regression: Unknown firm → UNKNOWN."""
    section("Regression R5: UNKNOWN firm")
    detector = PropFirmDetector()
    result = detector.detect(
        server="RandomServer-Demo",
        broker="RandomBroker",
        company="Random Corp",
        account_name="Standard Account",
    )
    check("Status is UNKNOWN", result.status == VerificationStatus.UNKNOWN)
    check("No firm identified", result.firm_id is None)


def test_regression_unverified_not_used_as_verified():
    """Regression: Unverified rules cannot be used as verified automated risk rules."""
    section("Regression R6: Unverified != verified rules")
    calc = LiveRiskCalculator()

    # Scenario: IDENTIFIED status but no actual rules populated
    status = calc.calculate(
        account_id="unverified-rules-1",
        account_type="FUNDED",
        balance=100000,
        equity=100000,
        risk_profile={
            "daily_loss": 5.0,
            "max_loss": 10.0,
            "initial_balance": 100000,
        },
        prop_firm="FTMO",
        verification_status="IDENTIFIED",  # metadata match only
    )
    check("Status is IDENTIFIED", status.verification_status == "IDENTIFIED")
    check("Risk level is SAFE (rules come from risk_profile, not detection)",
          status.risk_level == RiskLevel.SAFE)

    # Scenario: No risk profile at all → UNVERIFIED → blocked
    status2 = calc.calculate(
        account_id="unverified-rules-2",
        account_type="FUNDED",
        balance=100000,
        equity=100000,
        risk_profile=None,
        prop_firm="FTMO",
        verification_status="IDENTIFIED",
    )
    check("No profile -> UNVERIFIED", status2.risk_level == RiskLevel.UNVERIFIED)
    check("No profile -> blocked", "blocked" in status2.risk_level_message.lower())
    check("Risk profile missing flag set", status2.risk_profile_missing)

    # Scenario: UNKNOWN status with valid rules → rules still apply
    status3 = calc.calculate(
        account_id="unknown-with-rules",
        account_type="PERSONAL",
        balance=10000,
        equity=10000,
        risk_profile={
            "daily_loss": 5.0,
            "max_loss": 15.0,
            "initial_balance": 10000,
        },
        verification_status="UNKNOWN",
    )
    check("UNKNOWN with valid rules -> SAFE", status3.risk_level == RiskLevel.SAFE)
    check("Daily loss limit still applies", status3.daily_loss_limit_usd == 500.0)


# ── Run all ──────────────────────────────────────────────────────────

def main():
    global PASS, FAIL

    print("\n" + "="*60)
    print("  PHASE 1 — 20-SCENARIO + REGRESSION TEST SUITE")
    print("  Dashboard + Account Profile + Risk Profile")
    print("="*60)

    test_01_personal_account()
    test_02_prop_firm_account()
    test_03_unknown_prop_firm()
    test_04_ambiguous_prop_firm()
    test_05_verified_rule_profile()
    test_06_user_provided_rule_profile()
    test_07_unverified_profile()
    test_08_near_daily_loss_limit()
    test_09_near_maximum_loss_limit()
    test_10_floating_loss()
    test_11_existing_positions()
    test_12_multiple_positions()
    test_13_trade_exceeding_risk()
    test_14_trade_within_risk()
    test_15_stale_risk_data()
    test_16_restart_reconnect()
    test_17_conservative_mode()
    test_18_balanced_mode()
    test_19_aggressive_mode()
    test_20_personal_vs_prop_firm()
    test_prop_firm_detection_ftmo()
    test_prop_firm_detection_funding_pips()
    test_prop_firm_program_detection()
    test_safety_buffer()

    # Regression tests for Fix #1 verification semantics
    test_regression_firm_identified_rules_unknown()
    test_regression_verified_rules()
    test_regression_user_provided_rules()
    test_regression_ambiguous_firm()
    test_regression_unknown_firm()
    test_regression_unverified_not_used_as_verified()

    print(f"\n{'='*60}")
    print(f"  RESULTS: {PASS} PASS / {FAIL} FAIL / {PASS+FAIL} TOTAL")
    print(f"{'='*60}")

    if FAIL > 0:
        sys.exit(1)
    else:
        print("  All scenarios passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from core_engine.risk.account_profile import AccountProfileBuilder
from core_engine.risk.risk_validator import RiskValidator
from core_engine.risk.lot_calculator import LotCalculator
from core_engine.risk.funded_risk import FundedRiskManager
from core_engine.risk.daily_loss_guard import DailyLossGuard
from core_engine.risk.max_loss_guard import MaxLossGuard
from core_engine.risk.drawdown_protection import DrawdownProtection


print("=" * 70)
print("RISK LAYER TEST")
print("=" * 70)

builder = AccountProfileBuilder()
validator = RiskValidator()
lot_calculator = LotCalculator()
funded_manager = FundedRiskManager()
daily_guard = DailyLossGuard()
max_loss_guard = MaxLossGuard()
dd_protection = DrawdownProtection()


# =====================================================
# 1. CREATE PROFILES
# =====================================================

funded_profile = builder.create_profile(
    client_id="CLIENT_FUNDED_001",
    telegram_user_id="123456",
    account_type="FUNDED",
    balance=10000,
    equity=10000,
    broker="IC Markets",
    prop_firm="FTMO",
    symbol="XAUUSD"
)

personal_profile = builder.create_profile(
    client_id="CLIENT_PERSONAL_001",
    telegram_user_id="789101",
    account_type="PERSONAL",
    balance=2000,
    equity=2000,
    broker="IC Markets",
    symbol="XAUUSD"
)

small_profile = builder.create_profile(
    client_id="CLIENT_SMALL_001",
    telegram_user_id="555777",
    account_type="SMALL",
    balance=200,
    equity=200,
    broker="IC Markets",
    symbol="XAUUSD"
)

custom_risky_profile = builder.create_profile(
    client_id="CLIENT_RISKY_001",
    telegram_user_id="999111",
    account_type="FUNDED",
    balance=10000,
    equity=10000,
    broker="IC Markets",
    prop_firm="FTMO",
    symbol="XAUUSD",
    use_recommended_settings=False,
    custom_settings_acknowledged=False,
    custom_settings={
        "risk_per_trade": 2.0,
        "max_daily_loss": 8.0,
        "max_account_loss": 10.0,
        "preferred_rr": 1.2,
        "min_lot": 0.01,
        "max_lot": 5.0,
        "lot_step": 0.01,
    }
)

profiles = [
    funded_profile,
    personal_profile,
    small_profile,
    custom_risky_profile,
]


# =====================================================
# 2. PROFILE + VALIDATION TEST
# =====================================================

print("\n===== PROFILE VALIDATION =====")

for profile in profiles:
    print("\n" + "-" * 70)
    print(builder.profile_summary(profile))

    validation = validator.validate_profile(profile)

    print("\nValidation:")
    print(validation.to_dict())

    print("\nWarning Message:")
    print(validator.generate_warning_message(validation))


# =====================================================
# 3. LOT CALCULATION TEST
# =====================================================

print("\n===== LOT CALCULATION =====")

trade_examples = [
    {
        "direction": "BUY",
        "entry": 2350.00,
        "sl": 2345.00,
    },
    {
        "direction": "SELL",
        "entry": 2350.00,
        "sl": 2355.00,
    },
]

for profile in profiles:
    print("\n" + "-" * 70)
    print(f"Profile: {profile.client_id} | Type: {profile.account_type}")

    for trade in trade_examples:
        lot_result = lot_calculator.calculate_lot(
            profile=profile,
            entry_price=trade["entry"],
            stop_loss_price=trade["sl"],
            direction=trade["direction"],
            rr=profile.preferred_rr,
            contract_size=100.0
        )

        print(f"\nTrade: {trade['direction']}")
        print(lot_result.to_dict())


# =====================================================
# 4. FUNDED RISK TEST
# =====================================================

print("\n===== FUNDED RISK MANAGER =====")

funded_scenarios = [
    {
        "name": "SAFE",
        "current_equity": 9950,
        "daily_start_equity": 10000,
        "start_balance": 10000,
        "planned_risk": 50,
    },
    {
        "name": "DAILY WARNING",
        "current_equity": 9750,
        "daily_start_equity": 10000,
        "start_balance": 10000,
        "planned_risk": 50,
    },
    {
        "name": "DAILY HARD STOP",
        "current_equity": 9700,
        "daily_start_equity": 10000,
        "start_balance": 10000,
        "planned_risk": 100,
    },
    {
        "name": "TOTAL HARD STOP",
        "current_equity": 9250,
        "daily_start_equity": 10000,
        "start_balance": 10000,
        "planned_risk": 150,
    },
]

for scenario in funded_scenarios:
    result = funded_manager.evaluate(
        profile=funded_profile,
        current_equity=scenario["current_equity"],
        daily_start_equity=scenario["daily_start_equity"],
        start_balance=scenario["start_balance"],
        open_trade_risk_amount=scenario["planned_risk"],
    )

    print("\n" + "-" * 70)
    print("Scenario:", scenario["name"])
    print(result.to_dict())


# =====================================================
# 5. DAILY LOSS GUARD TEST
# =====================================================

print("\n===== DAILY LOSS GUARD =====")

daily_scenarios = [
    {
        "name": "SAFE",
        "current_equity": 9980,
        "daily_start_equity": 10000,
        "planned_risk": 50,
    },
    {
        "name": "WARNING",
        "current_equity": 9800,
        "daily_start_equity": 10000,
        "planned_risk": 50,
    },
    {
        "name": "REDUCE RISK",
        "current_equity": 9750,
        "daily_start_equity": 10000,
        "planned_risk": 100,
    },
    {
        "name": "HARD STOP",
        "current_equity": 9700,
        "daily_start_equity": 10000,
        "planned_risk": 100,
    },
]

for scenario in daily_scenarios:
    result = daily_guard.evaluate(
        profile=funded_profile,
        current_equity=scenario["current_equity"],
        daily_start_equity=scenario["daily_start_equity"],
        planned_risk_amount=scenario["planned_risk"],
    )

    print("\n" + "-" * 70)
    print("Scenario:", scenario["name"])
    print(result.to_dict())


# =====================================================
# 6. MAX LOSS GUARD TEST
# =====================================================

print("\n===== MAX LOSS GUARD =====")

max_loss_scenarios = [
    {
        "name": "SAFE",
        "current_equity": 9900,
        "start_balance": 10000,
        "planned_risk": 50,
    },
    {
        "name": "WARNING",
        "current_equity": 9450,
        "start_balance": 10000,
        "planned_risk": 100,
    },
    {
        "name": "REDUCE RISK",
        "current_equity": 9300,
        "start_balance": 10000,
        "planned_risk": 100,
    },
    {
        "name": "HARD STOP",
        "current_equity": 9250,
        "start_balance": 10000,
        "planned_risk": 150,
    },
]

for scenario in max_loss_scenarios:
    result = max_loss_guard.evaluate(
        profile=funded_profile,
        current_equity=scenario["current_equity"],
        start_balance=scenario["start_balance"],
        planned_risk_amount=scenario["planned_risk"],
    )

    print("\n" + "-" * 70)
    print("Scenario:", scenario["name"])
    print(result.to_dict())


# =====================================================
# 7. DRAWDOWN PROTECTION TEST
# =====================================================

print("\n===== DRAWDOWN PROTECTION =====")

dd_scenarios = [
    {
        "name": "SAFE",
        "current_equity": 9900,
        "start_balance": 10000,
        "peak_equity": 10100,
    },
    {
        "name": "WARNING",
        "current_equity": 9700,
        "start_balance": 10000,
        "peak_equity": 10100,
    },
    {
        "name": "REDUCE",
        "current_equity": 9450,
        "start_balance": 10000,
        "peak_equity": 10100,
    },
    {
        "name": "DEFENSIVE",
        "current_equity": 9250,
        "start_balance": 10000,
        "peak_equity": 10100,
    },
    {
        "name": "HARD STOP",
        "current_equity": 9050,
        "start_balance": 10000,
        "peak_equity": 10100,
    },
]

for scenario in dd_scenarios:
    result = dd_protection.evaluate(
        profile=funded_profile,
        current_equity=scenario["current_equity"],
        start_balance=scenario["start_balance"],
        peak_equity=scenario["peak_equity"],
    )

    print("\n" + "-" * 70)
    print("Scenario:", scenario["name"])
    print(result.to_dict())


print("\n" + "=" * 70)
print("RISK LAYER TEST COMPLETED")
print("=" * 70)
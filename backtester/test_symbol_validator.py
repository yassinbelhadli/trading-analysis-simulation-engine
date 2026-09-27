from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from core_engine.risk.symbol_validator import SymbolValidator
from core_engine.risk.account_profile import AccountProfileBuilder


print("=" * 70)
print("SYMBOL VALIDATOR TEST")
print("=" * 70)

validator = SymbolValidator()
builder = AccountProfileBuilder()


# =====================================================
# 1. NORMALIZATION TEST
# =====================================================

symbols_to_test = [
    "XAUUSD",
    "XAUUSDm",
    "XAUUSD.cash",
    "GOLD",
    "GOLDmicro",
    "NAS100",
    "NAS100m",
    "US100",
    "USTEC",
    "USTEC.cash",
    "NASDAQ",
    "NDX",
    "EURUSD",
    "GBPUSD",
    "BTCUSD",
    "ETHUSD",
    "US30",
    "US500",
    "GER40",
    "XAGUSD",
    "SILVER",
]

print("\n===== NORMALIZE SYMBOLS =====")

for symbol in symbols_to_test:
    normalized = validator.normalize_symbol(symbol)
    market = validator.classify_symbol_market(symbol)
    supported = validator.is_supported_market(symbol)

    print(
        f"{symbol:15} -> normalized={normalized:8} | "
        f"market={str(market):8} | supported={supported}"
    )


# =====================================================
# 2. BROKER SCAN TESTS
# =====================================================

broker_cases = {
    "EXNESS_GOLD_ONLY": [
        "EURUSD",
        "GBPUSD",
        "XAUUSDm",
        "US30",
        "BTCUSD",
    ],
    "IC_MARKETS_GOLD_AND_NASDAQ": [
        "EURUSD",
        "XAUUSD",
        "NAS100",
        "US500",
        "GER40",
    ],
    "FTMO_STYLE": [
        "EURUSD",
        "XAUUSD.cash",
        "US100.cash",
        "GER40.cash",
    ],
    "NASDAQ_ONLY": [
        "EURUSD",
        "USTEC",
        "US30",
        "BTCUSD",
    ],
    "UNSUPPORTED_ONLY": [
        "EURUSD",
        "GBPUSD",
        "BTCUSD",
        "US30",
        "US500",
        "GER40",
        "XAGUSD",
    ],
    "EMPTY_SYMBOLS": [],
}

print("\n===== BROKER SYMBOL DETECTION =====")

for case_name, broker_symbols in broker_cases.items():
    print("\n" + "-" * 70)
    print("CASE:", case_name)

    result = validator.detect_supported_symbols(
        broker_symbols=broker_symbols,
        prefer_gold_first=True
    )

    print(result.to_dict())
    print("\nTelegram Message:")
    print(validator.generate_telegram_message(result))


# =====================================================
# 3. UPDATE ACCOUNT PROFILE WITH DETECTED SYMBOLS
# =====================================================

print("\n===== ACCOUNT PROFILE SYMBOL UPDATE =====")

profile = builder.create_profile(
    client_id="CLIENT_SYMBOL_TEST_001",
    telegram_user_id="123456",
    account_type="FUNDED",
    balance=10000,
    equity=10000,
    broker="IC Markets",
    prop_firm="FTMO",
    symbol="XAUUSD",
)

broker_symbols = [
    "EURUSD",
    "GBPUSD",
    "XAUUSD.cash",
    "US100.cash",
    "US30.cash",
]

scan = validator.detect_supported_symbols(broker_symbols)

updated_profile = builder.update_symbols(
    profile=profile,
    detected_symbols=scan.detected_symbols,
    allowed_symbols=scan.allowed_symbols,
    enabled_markets=scan.enabled_markets,
    primary_symbol=scan.primary_symbol,
)

print(builder.profile_summary(updated_profile))


# =====================================================
# 4. SYMBOL ALLOWED CHECK
# =====================================================

print("\n===== SYMBOL ALLOWED CHECK =====")

allowed_symbols = updated_profile.allowed_symbols

test_trade_symbols = [
    "XAUUSD",
    "XAUUSD.cash",
    "XAUUSDm",
    "US100",
    "US100.cash",
    "USTEC",
    "NAS100",
    "EURUSD",
    "BTCUSD",
    "US30",
]

for symbol in test_trade_symbols:
    print(
        f"{symbol:12} allowed={validator.is_symbol_allowed(symbol, allowed_symbols)} "
        f"normalized={validator.normalize_symbol(symbol)} "
        f"market={validator.classify_symbol_market(symbol)}"
    )


print("\n" + "=" * 70)
print("SYMBOL VALIDATOR TEST COMPLETED")
print("=" * 70)
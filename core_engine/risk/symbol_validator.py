# symbol_validator.py
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional


@dataclass
class SymbolDetectionResult:
    tradable: bool
    primary_symbol: Optional[str]
    allowed_symbols: List[str]
    detected_symbols: List[str]
    enabled_markets: List[str]
    disabled_markets: List[str]
    reason: str
    warning: Optional[str] = None
    normalized_primary_symbol: Optional[str] = None
    normalized_allowed_symbols: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SymbolValidator:
    def __init__(self):
        self.gold_keywords = ["XAU", "GOLD"]

        self.nasdaq_keywords = [
            "NAS100", "NAS", "US100", "USTEC", "NASDAQ", "NDX"
        ]

        self.crypto_keywords = [
            "BTC", "BTCUSD", "BTCUSDT", "XBT", "XBTUSD", "BITCOIN"
        ]

        self.excluded_keywords = [
            "XAUEUR",
            "XAUGBP",
            "XAUAUD",
            "XAG",
            "SILVER",
            "COPPER",
            "US30",
            "US500",
            "SPX",
            "SP500",
            "GER40",
            "DAX",
            "ETH",
            "ETHUSD",
        ]

    def _clean_symbol(self, symbol: str) -> str:
        return str(symbol).upper().strip()

    def normalize_symbol(self, broker_symbol: str) -> str:
        s = self._clean_symbol(broker_symbol)

        if self._is_excluded(s):
            return "UNKNOWN"

        if "XAU" in s or "GOLD" in s:
            return "XAUUSD"

        if (
            "NAS100" in s
            or "US100" in s
            or "USTEC" in s
            or "NASDAQ" in s
            or "NDX" in s
        ):
            return "NAS100"

        if (
            "BTC" in s
            or "BTCUSD" in s
            or "BTCUSDT" in s
            or "XBT" in s
            or "XBTUSD" in s
            or "BITCOIN" in s
        ):
            return "BTCUSD"

        return "UNKNOWN"

    def _is_excluded(self, symbol: str) -> bool:
        s = self._clean_symbol(symbol)
        return any(x in s for x in self.excluded_keywords)

    def _score_symbol_quality(self, symbol: str, market: str) -> int:
        s = self._clean_symbol(symbol)
        score = 0

        if market == "GOLD":
            if s == "XAUUSD":
                score += 120
            elif s.startswith("XAUUSD"):
                score += 100
            elif "XAU" in s:
                score += 80
            elif "GOLD" in s:
                score += 60

        elif market == "NASDAQ":
            if s in ["NAS100", "US100", "USTEC"]:
                score += 120
            elif s.startswith("NAS100"):
                score += 100
            elif s.startswith("US100"):
                score += 95
            elif s.startswith("USTEC"):
                score += 90
            elif "NASDAQ" in s:
                score += 75
            elif "NDX" in s:
                score += 70

        elif market == "CRYPTO":
            if s in ["BTCUSD", "BTCUSDm".upper(), "BTCUSDT", "XBTUSD"]:
                score += 120
            elif s.startswith("BTCUSD"):
                score += 110
            elif s.startswith("BTCUSDT"):
                score += 100
            elif s.startswith("XBTUSD"):
                score += 95
            elif "BTC" in s:
                score += 80
            elif "BITCOIN" in s:
                score += 70

        if "." in s or "_" in s or "-" in s:
            score += 5

        bad_suffixes = ["MICRO", "MINI", "PRO", "RAW", "ECN"]
        for b in bad_suffixes:
            if b in s:
                score -= 10

        return score

    def _select_best_symbol(self, symbols: List[str], market: str) -> Optional[str]:
        if not symbols:
            return None

        ranked = sorted(
            symbols,
            key=lambda x: self._score_symbol_quality(x, market),
            reverse=True
        )
        return ranked[0]

    def detect_supported_symbols(
        self,
        broker_symbols: List[str],
        prefer_gold_first: bool = True
    ) -> SymbolDetectionResult:

        if not broker_symbols:
            return SymbolDetectionResult(
                tradable=False,
                primary_symbol=None,
                allowed_symbols=[],
                detected_symbols=[],
                enabled_markets=[],
                disabled_markets=["GOLD", "NASDAQ", "CRYPTO"],
                reason="NO_BROKER_SYMBOLS_FOUND",
                warning="MT5 returned no symbols. Bot cannot trade.",
                normalized_primary_symbol=None,
                normalized_allowed_symbols=[],
            )

        cleaned_symbols = [self._clean_symbol(s) for s in broker_symbols]

        gold_symbols = []
        nasdaq_symbols = []
        crypto_symbols = []

        for symbol in cleaned_symbols:
            normalized = self.normalize_symbol(symbol)

            if normalized == "XAUUSD":
                gold_symbols.append(symbol)
            elif normalized == "NAS100":
                nasdaq_symbols.append(symbol)
            elif normalized == "BTCUSD":
                crypto_symbols.append(symbol)

        best_gold = self._select_best_symbol(gold_symbols, "GOLD")
        best_nasdaq = self._select_best_symbol(nasdaq_symbols, "NASDAQ")
        best_crypto = self._select_best_symbol(crypto_symbols, "CRYPTO")

        allowed_symbols = []
        enabled_markets = []
        disabled_markets = []

        if best_gold:
            allowed_symbols.append(best_gold)
            enabled_markets.append("GOLD")
        else:
            disabled_markets.append("GOLD")

        if best_nasdaq:
            allowed_symbols.append(best_nasdaq)
            enabled_markets.append("NASDAQ")
        else:
            disabled_markets.append("NASDAQ")

        if best_crypto:
            allowed_symbols.append(best_crypto)
            enabled_markets.append("CRYPTO")
        else:
            disabled_markets.append("CRYPTO")

        if not allowed_symbols:
            return SymbolDetectionResult(
                tradable=False,
                primary_symbol=None,
                allowed_symbols=[],
                detected_symbols=cleaned_symbols,
                enabled_markets=[],
                disabled_markets=disabled_markets,
                reason="NO_SUPPORTED_MARKET_FOUND",
                warning="Broker does not provide supported Gold, Nasdaq, or BTC symbols.",
                normalized_primary_symbol=None,
                normalized_allowed_symbols=[],
            )

        if prefer_gold_first and best_gold:
            primary_symbol = best_gold
        elif best_nasdaq:
            primary_symbol = best_nasdaq
        elif best_crypto:
            primary_symbol = best_crypto
        else:
            primary_symbol = allowed_symbols[0]

        normalized_primary = self.normalize_symbol(primary_symbol)

        normalized_allowed = []
        for symbol in allowed_symbols:
            normalized = self.normalize_symbol(symbol)
            if normalized != "UNKNOWN" and normalized not in normalized_allowed:
                normalized_allowed.append(normalized)

        warning = None
        if len(enabled_markets) == 1:
            warning = f"Only {enabled_markets[0]} is available. Bot will trade this market only."

        return SymbolDetectionResult(
            tradable=True,
            primary_symbol=primary_symbol,
            allowed_symbols=allowed_symbols,
            detected_symbols=cleaned_symbols,
            enabled_markets=enabled_markets,
            disabled_markets=disabled_markets,
            reason="SUPPORTED_SYMBOLS_FOUND",
            warning=warning,
            normalized_primary_symbol=normalized_primary,
            normalized_allowed_symbols=normalized_allowed,
        )

    def is_symbol_allowed(self, symbol: str, allowed_symbols: List[str]) -> bool:
        s = self._clean_symbol(symbol)
        normalized = self.normalize_symbol(s)

        allowed_clean = [self._clean_symbol(x) for x in allowed_symbols]
        allowed_normalized = [self.normalize_symbol(x) for x in allowed_symbols]

        return s in allowed_clean or normalized in allowed_normalized

    def classify_symbol_market(self, symbol: str) -> Optional[str]:
        normalized = self.normalize_symbol(symbol)

        if normalized == "XAUUSD":
            return "GOLD"

        if normalized == "NAS100":
            return "NASDAQ"

        if normalized == "BTCUSD":
            return "CRYPTO"

        return None

    def is_supported_market(self, symbol: str) -> bool:
        return self.normalize_symbol(symbol) in ["XAUUSD", "NAS100", "BTCUSD"]

    def generate_telegram_message(self, result: SymbolDetectionResult) -> str:
        if not result.tradable:
            return (
                "❌ No supported market found.\n"
                "The bot supports Gold, Nasdaq and BTC only.\n"
                f"Reason: {result.reason}"
            )

        lines = [
            "✅ Broker scan completed.",
            f"Primary Broker Symbol: {result.primary_symbol}",
            f"Normalized Symbol: {result.normalized_primary_symbol}",
            f"Enabled Markets: {', '.join(result.enabled_markets)}",
            f"Allowed Broker Symbols: {', '.join(result.allowed_symbols)}",
        ]

        if result.normalized_allowed_symbols:
            lines.append(
                f"Bot Standard Symbols: {', '.join(result.normalized_allowed_symbols)}"
            )

        if result.disabled_markets:
            lines.append(f"Disabled Markets: {', '.join(result.disabled_markets)}")

        if result.warning:
            lines.append(f"⚠️ {result.warning}")

        return "\n".join(lines)
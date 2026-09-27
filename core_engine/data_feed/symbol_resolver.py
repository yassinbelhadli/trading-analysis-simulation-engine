import re
from dataclasses import dataclass
from typing import Any, Iterable, Optional

from core_engine.data_feed.symbol_aliases import MARKET_ALIASES


@dataclass
class ResolvedSymbol:
    market: str
    symbol: Optional[str]
    score: int
    matched_alias: Optional[str]
    reason: str


def extract_symbol_name(item: Any) -> Optional[str]:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        value = item.get("name") or item.get("symbol")
        return str(value).strip() if value else None
    value = getattr(item, "name", None) or getattr(item, "symbol", None)
    return str(value).strip() if value else None


def normalize_symbol(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def _is_excluded(normalized: str, excluded: list[str]) -> bool:
    for value in excluded:
        target = normalize_symbol(value)
        if normalized == target:
            return True
    return False


def _match_score(
    original: str,
    normalized: str,
    exact_aliases: list[str],
    prefixes: list[str],
) -> tuple[int, Optional[str], str]:
    best_score = 0
    best_alias = None
    best_reason = "No match"

    for alias in exact_aliases:
        target = normalize_symbol(alias)
        if normalized == target:
            return 100, alias, "Exact match"

    for alias in prefixes:
        target = normalize_symbol(alias)
        if len(target) < 4:
            continue
        if normalized.startswith(target):
            score = 90
            suffix = normalized[len(target):]
            if suffix in {
                "", "RAW", "ECN", "C", "M", "I", "STND", "STD",
                "PRO", "CASH", "FUT", "CR", "CRYPTO",
            }:
                score = 95
            if score > best_score:
                best_score = score
                best_alias = alias
                best_reason = f"Prefix match: {alias}"
        elif target in normalized:
            score = 65
            if score > best_score:
                best_score = score
                best_alias = alias
                best_reason = f"Contains alias: {alias}"

    return best_score, best_alias, best_reason


def resolve_market_symbol(
    symbols: Iterable[Any],
    market: str,
) -> ResolvedSymbol:
    config = MARKET_ALIASES.get(market)
    if not config:
        return ResolvedSymbol(
            market=market, symbol=None, score=0,
            matched_alias=None, reason="Unknown market",
        )

    candidates = []
    for item in symbols:
        original = extract_symbol_name(item)
        if not original:
            continue
        normalized = normalize_symbol(original)
        if _is_excluded(normalized, config.get("exclude", [])):
            continue
        score, alias, reason = _match_score(
            original=original,
            normalized=normalized,
            exact_aliases=config.get("exact", []),
            prefixes=config.get("prefixes", []),
        )
        if score > 0:
            candidates.append((score, len(original), original, alias, reason))

    if not candidates:
        return ResolvedSymbol(
            market=market, symbol=None, score=0,
            matched_alias=None, reason="No supported symbol found",
        )

    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
    score, _, original, alias, reason = candidates[0]

    return ResolvedSymbol(
        market=market,
        symbol=original,
        score=score,
        matched_alias=alias,
        reason=reason,
    )


def resolve_required_markets(symbols: Iterable[Any]) -> dict[str, ResolvedSymbol]:
    return {
        "GOLD": resolve_market_symbol(symbols, "GOLD"),
        "NASDAQ": resolve_market_symbol(symbols, "NASDAQ"),
        "BITCOIN": resolve_market_symbol(symbols, "BITCOIN"),
    }

"""Economic Calendar — single source of truth for US economic events.

Provides:
  - Normalized EconomicEvent dataclass (provider-agnostic)
  - Deterministic impact classification (configurable)
  - Market relevance mapping (XAUUSD / BTCUSD / NASDAQ)
  - EconomicCalendarService (fetch → normalize → upsert → deduplicate)
  - Stale-data policy (FRESH / STALE / UNAVAILABLE)
  - Scheduler interfaces (Phase 3 implementation point)
"""

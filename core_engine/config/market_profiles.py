# market_profiles.py

MARKET_PROFILES = {
    "XAUUSD": {
        "sell_fvg_min_score": 72.0,
        "sell_ob_min_score": 80.0,
        "buy_fvg_min_score": 75.0,
        "buy_ob_min_score": 70.0,
    },

    "NAS100": {
        "sell_fvg_min_score": 72.0,
        "sell_ob_min_score": 80.0,
        "buy_fvg_min_score": 75.0,
        "buy_ob_min_score": 70.0,
    },

    "BTCUSD": {
        "sell_fvg_min_score": 65,
        "sell_ob_min_score": 68,
        "buy_fvg_min_score": 62,
        "buy_ob_min_score": 62,
}
}


def get_market_profile(normalized_symbol: str):
    return MARKET_PROFILES.get(normalized_symbol, MARKET_PROFILES["XAUUSD"])
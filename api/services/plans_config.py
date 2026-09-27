"""
Plan definitions — each plan's feature set, pricing, and limits.
The plan name stored on License/Subscription determines available features.
"""

PLANS: dict[str, dict] = {
    "starter": {
        "name": "Starter",
        "price_monthly": 29,
        "price_yearly": 290,
        "max_accounts": 1,
        "max_daily_loss": 1000,
        "max_risk_per_trade": 1.0,
        "features": {
            "xauusd": True,
            "nas100": True,
            "multi_account": False,
            "telegram_alerts": True,
            "analytics": False,
            "api_access": False,
            "priority_support": False,
        },
    },
    "professional": {
        "name": "Professional",
        "price_monthly": 59,
        "price_yearly": 590,
        "max_accounts": 3,
        "max_daily_loss": 3000,
        "max_risk_per_trade": 2.0,
        "features": {
            "xauusd": True,
            "nas100": True,
            "multi_account": True,
            "telegram_alerts": True,
            "analytics": True,
            "api_access": False,
            "priority_support": False,
        },
    },
    "premium": {
        "name": "Premium",
        "price_monthly": 99,
        "price_yearly": 990,
        "max_accounts": 10,
        "max_daily_loss": 10000,
        "max_risk_per_trade": 5.0,
        "features": {
            "xauusd": True,
            "nas100": True,
            "multi_account": True,
            "telegram_alerts": True,
            "analytics": True,
            "api_access": True,
            "priority_support": True,
        },
    },
    "enterprise": {
        "name": "Enterprise",
        "price_monthly": None,
        "price_yearly": None,
        "one_time_price": 999,
        "max_accounts": 999,
        "max_daily_loss": 100000,
        "max_risk_per_trade": 10.0,
        "features": {
            "xauusd": True,
            "nas100": True,
            "multi_account": True,
            "telegram_alerts": True,
            "analytics": True,
            "api_access": True,
            "priority_support": True,
        },
    },
}


def get_plan(plan_name: str) -> dict | None:
    return PLANS.get(plan_name)


def get_plan_features(plan_name: str) -> dict:
    plan = PLANS.get(plan_name)
    if not plan:
        return {}
    return plan.get("features", {})


def has_feature(plan_name: str, feature: str) -> bool:
    features = get_plan_features(plan_name)
    return features.get(feature, False)

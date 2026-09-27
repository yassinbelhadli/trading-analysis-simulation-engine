from copy import deepcopy


DEFAULT_SETUP = {
    "language": "EN",

    "license": {
        "verified": False,
        "plan": None,
    },

    "account": {
        "type": None,          # PERSONAL / FUNDED
        "balance": None,
        "currency": "USD",
    },

    "broker": {
        "id": None,
        "name": None,
    },

    "prop_firm": {
        "id": None,
        "name": None,
        "challenge_type": None,
    },

    "trading": {
        "mode": None,
    },

    "platform": {
        "type": None,          # MT4 / MT5
        "server": None,
        "login": None,
        "password": None,
    },

    "risk": {
        "daily_loss": None,
        "max_loss": None,
        "profit_target": None,
        "min_trades": None,
    },

    "preferences": {
        "language": "EN",
        "notifications": True,
    },
}


def get_setup(context):
    if "setup" not in context.user_data:
        context.user_data["setup"] = deepcopy(DEFAULT_SETUP)

    for key, value in DEFAULT_SETUP.items():
        if key not in context.user_data["setup"]:
            context.user_data["setup"][key] = deepcopy(value)

    return context.user_data["setup"]
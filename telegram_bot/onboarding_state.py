from dataclasses import dataclass
from enum import Enum
from typing import Dict, List


class OnboardingState(str, Enum):

    START = "START"

    SELECT_LANGUAGE = "SELECT_LANGUAGE"

    CHECK_LICENSE = "CHECK_LICENSE"

    SUBSCRIPTION_REQUIRED = "SUBSCRIPTION_REQUIRED"

    SELECT_ACCOUNT_TYPE = "SELECT_ACCOUNT_TYPE"

    SELECT_BROKER = "SELECT_BROKER"
    CUSTOM_BROKER = "CUSTOM_BROKER"

    SELECT_PROP_FIRM = "SELECT_PROP_FIRM"
    CUSTOM_PROP_FIRM = "CUSTOM_PROP_FIRM"

    SELECT_FUNDED_SIZE = "SELECT_FUNDED_SIZE"

    CUSTOM_FUNDED_RULES = "CUSTOM_FUNDED_RULES"

    SELECT_TRADING_MODE = "SELECT_TRADING_MODE"

    ACCOUNT_BALANCE = "ACCOUNT_BALANCE"

    MT5_WARNING = "MT5_WARNING"

    MT5_LOGIN = "MT5_LOGIN"

    TERMS_CONFIRMATION = "TERMS_CONFIRMATION"

    COMPLETED = "COMPLETED"

    MAIN_MENU = "MAIN_MENU"


LANGUAGES = {
    "EN": "🇺🇸 English",
    "FR": "🇫🇷 Français",
    "AR": "🇲🇦 العربية",
    "ES": "🇪🇸 Español",
}


ACCOUNT_TYPES = {
    "PERSONAL": "Personal Account",
    "FUNDED": "Funded Account",
}


TRADING_MODES = {
    "ULTRA_CONSERVATIVE": {
        "title": "Ultra Conservative",
        "description": "Maximum protection. Lowest risk.",
    },
    "CONSERVATIVE": {
        "title": "Conservative",
        "description": "Low risk with strict confirmations.",
    },
    "BALANCED": {
        "title": "Balanced",
        "description": "Recommended for most traders.",
    },
    "AGGRESSIVE": {
        "title": "Aggressive",
        "description": "Higher frequency and dynamic risk.",
    },
}


POPULAR_BROKERS = [
    "IC Markets",
    "Pepperstone",
    "Exness",
    "XM",
    "Eightcap",
    "BlackBull",
    "Fusion Markets",
    "FP Markets",
    "Other",
]


POPULAR_PROP_FIRMS = [
    "FTMO",
    "FundedNext",
    "Funded Trading Plus",
    "FundedPips",
    "The5ers",
    "Blueberry Funded",
    "TopstepX",
    "Other",
]


FUNDED_ACCOUNT_SIZES = [
    "5K",
    "10K",
    "25K",
    "50K",
    "100K",
    "200K",
    "300K",
    "500K",
]


@dataclass
class UserOnboardingSession:

    telegram_user_id: str

    state: OnboardingState

    data: Dict

    def next(self, new_state: OnboardingState):

        self.state = new_state

    def save(self, key, value):

        self.data[key] = value
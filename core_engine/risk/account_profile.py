# account_profile.py
from dataclasses import dataclass, asdict, field
from enum import Enum
from typing import Dict, Any, Optional, List
import json


class AccountType(str, Enum):
    FUNDED = "FUNDED"
    PERSONAL = "PERSONAL"
    SMALL = "SMALL"


@dataclass
class AccountProfile:
    client_id: str
    account_type: str

    balance: float
    equity: float

    risk_per_trade: float
    max_daily_loss: float
    max_account_loss: float

    preferred_rr: float

    min_lot: float
    max_lot: float
    lot_step: float

    currency: str = "USD"

    # Default / primary trading symbol
    symbol: str = "XAUUSD"

    # Auto symbol detection for SaaS / broker compatibility
    auto_detect_symbols: bool = True
    primary_symbol: Optional[str] = None
    allowed_symbols: List[str] = field(default_factory=list)
    detected_symbols: List[str] = field(default_factory=list)
    enabled_markets: List[str] = field(default_factory=list)

    use_recommended_settings: bool = True
    custom_settings_acknowledged: bool = False

    telegram_user_id: Optional[str] = None
    broker: Optional[str] = None
    prop_firm: Optional[str] = None

    is_active: bool = True

    # prop firm enforcement
    min_trading_days: Optional[int] = None
    profit_target: Optional[float] = None
    trading_days_count: int = 0
    first_trade_date: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=4)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "AccountProfile":
        return AccountProfile(**data)


class AccountProfileBuilder:
    def __init__(self):
        self.recommendations = {
            AccountType.FUNDED.value: {
                "risk_per_trade": 0.50,
                "max_daily_loss": 3.00,
                "max_account_loss": 8.00,
                "preferred_rr": 2.50,
                "min_lot": 0.01,
                "max_lot": 2.00,
                "lot_step": 0.01,
            },
            AccountType.PERSONAL.value: {
                "risk_per_trade": 1.00,
                "max_daily_loss": 5.00,
                "max_account_loss": 15.00,
                "preferred_rr": 2.00,
                "min_lot": 0.01,
                "max_lot": 5.00,
                "lot_step": 0.01,
            },
            AccountType.SMALL.value: {
                "risk_per_trade": 0.50,
                "max_daily_loss": 3.00,
                "max_account_loss": 10.00,
                "preferred_rr": 2.00,
                "min_lot": 0.01,
                "max_lot": 0.10,
                "lot_step": 0.01,
            },
        }

    def normalize_account_type(self, account_type: str) -> str:
        account_type = str(account_type).upper().strip()

        if account_type not in [x.value for x in AccountType]:
            raise ValueError("Invalid account_type. Use: FUNDED, PERSONAL, or SMALL")

        return account_type

    def get_recommended_settings(self, account_type: str) -> Dict[str, float]:
        account_type = self.normalize_account_type(account_type)
        return self.recommendations[account_type].copy()

    def create_profile(
        self,
        client_id: str,
        account_type: str,
        balance: float,
        equity: Optional[float] = None,
        telegram_user_id: Optional[str] = None,
        broker: Optional[str] = None,
        prop_firm: Optional[str] = None,
        custom_settings: Optional[Dict[str, Any]] = None,
        use_recommended_settings: bool = True,
        custom_settings_acknowledged: bool = False,
        currency: str = "USD",
        symbol: str = "XAUUSD",
        auto_detect_symbols: bool = True,
        primary_symbol: Optional[str] = None,
        allowed_symbols: Optional[List[str]] = None,
        detected_symbols: Optional[List[str]] = None,
        enabled_markets: Optional[List[str]] = None,
        min_trading_days: Optional[int] = None,
        profit_target: Optional[float] = None,
        trading_days_count: int = 0,
        first_trade_date: Optional[str] = None,
    ) -> AccountProfile:

        account_type = self.normalize_account_type(account_type)

        if balance <= 0:
            raise ValueError("Balance must be greater than 0")

        if equity is None:
            equity = balance

        if equity <= 0:
            raise ValueError("Equity must be greater than 0")

        settings = self.get_recommended_settings(account_type)

        if custom_settings:
            settings.update(custom_settings)

        if allowed_symbols is None:
            allowed_symbols = []

        if detected_symbols is None:
            detected_symbols = []

        if enabled_markets is None:
            enabled_markets = []

        if primary_symbol is None:
            primary_symbol = symbol

        return AccountProfile(
            client_id=str(client_id),
            telegram_user_id=str(telegram_user_id) if telegram_user_id else None,
            account_type=account_type,

            balance=float(balance),
            equity=float(equity),

            risk_per_trade=float(settings["risk_per_trade"]),
            max_daily_loss=float(settings["max_daily_loss"]),
            max_account_loss=float(settings["max_account_loss"]),

            preferred_rr=float(settings["preferred_rr"]),

            min_lot=float(settings["min_lot"]),
            max_lot=float(settings["max_lot"]),
            lot_step=float(settings["lot_step"]),

            currency=currency,
            symbol=symbol,

            auto_detect_symbols=auto_detect_symbols,
            primary_symbol=primary_symbol,
            allowed_symbols=allowed_symbols,
            detected_symbols=detected_symbols,
            enabled_markets=enabled_markets,

            broker=broker,
            prop_firm=prop_firm,

            use_recommended_settings=use_recommended_settings,
            custom_settings_acknowledged=custom_settings_acknowledged,
            is_active=True,

            min_trading_days=min_trading_days,
            profit_target=profit_target,
            trading_days_count=trading_days_count,
            first_trade_date=first_trade_date,
        )

    def update_profile(
        self,
        profile: AccountProfile,
        updates: Dict[str, Any],
        custom_settings_acknowledged: bool = False
    ) -> AccountProfile:

        data = profile.to_dict()
        data.update(updates)

        data["custom_settings_acknowledged"] = custom_settings_acknowledged
        data["use_recommended_settings"] = False

        return AccountProfile.from_dict(data)

    def update_symbols(
        self,
        profile: AccountProfile,
        detected_symbols: List[str],
        allowed_symbols: List[str],
        enabled_markets: List[str],
        primary_symbol: Optional[str] = None
    ) -> AccountProfile:

        if primary_symbol is None:
            primary_symbol = allowed_symbols[0] if allowed_symbols else None

        updates = {
            "detected_symbols": detected_symbols,
            "allowed_symbols": allowed_symbols,
            "enabled_markets": enabled_markets,
            "primary_symbol": primary_symbol,
            "symbol": primary_symbol if primary_symbol else profile.symbol,
            "auto_detect_symbols": True,
        }

        data = profile.to_dict()
        data.update(updates)

        return AccountProfile.from_dict(data)

    def profile_summary(self, profile: AccountProfile) -> str:
        return (
            f"Account Profile\n"
            f"Client ID: {profile.client_id}\n"
            f"Type: {profile.account_type}\n"
            f"Balance: {profile.balance} {profile.currency}\n"
            f"Equity: {profile.equity} {profile.currency}\n"
            f"Risk/Trade: {profile.risk_per_trade}%\n"
            f"Max Daily Loss: {profile.max_daily_loss}%\n"
            f"Max Account Loss: {profile.max_account_loss}%\n"
            f"Preferred RR: 1:{profile.preferred_rr}\n"
            f"Lot Range: {profile.min_lot} - {profile.max_lot}\n"
            f"Lot Step: {profile.lot_step}\n"
            f"Primary Symbol: {profile.primary_symbol}\n"
            f"Allowed Symbols: {profile.allowed_symbols}\n"
            f"Detected Symbols: {profile.detected_symbols}\n"
            f"Enabled Markets: {profile.enabled_markets}\n"
            f"Auto Detect Symbols: {profile.auto_detect_symbols}\n"
            f"Recommended Settings: {profile.use_recommended_settings}\n"
            f"Custom Risk Accepted: {profile.custom_settings_acknowledged}"
        )
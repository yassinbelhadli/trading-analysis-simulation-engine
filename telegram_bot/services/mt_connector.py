from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Max time to wait for a real MT4/MT5 connection before failing gracefully.
CONNECT_TIMEOUT_SECONDS = 15


@dataclass
class MTLoginData:
    platform: str
    server: str
    login: str
    password: str

    def to_dict(self):
        return asdict(self)


@dataclass
class MTAccountScanResult:
    success: bool
    state: str
    message: str

    platform: str
    server: str
    login: str

    broker_name: Optional[str]
    account_balance: float
    account_equity: float
    account_currency: str

    detected_symbols: List[str]
    supported_markets: List[str]

    # Real connection details
    leverage: str = ""
    trade_mode: str = ""
    company: str = ""
    hedge_mode: str = ""
    timezone: str = ""
    build: int = 0

    warnings: List[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self):
        return asdict(self)


class MTConnector:
    SUPPORTED_PLATFORMS = ["MT5"]

    async def test_connection(self, login_data: MTLoginData) -> MTAccountScanResult:
        platform = str(login_data.platform).upper().strip()

        if platform not in self.SUPPORTED_PLATFORMS:
            return MTAccountScanResult(
                success=False, state="UNSUPPORTED_PLATFORM",
                message="Unsupported platform. Only MT5 is supported.",
                platform=platform, server=login_data.server, login=login_data.login,
                broker_name=None, account_balance=0.0, account_equity=0.0,
                account_currency="USD", detected_symbols=[], supported_markets=[],
                warnings=[], metadata={},
            )

        if not login_data.server or not login_data.login or not login_data.password:
            return MTAccountScanResult(
                success=False, state="MISSING_LOGIN_DATA",
                message="Server, login and password are required.",
                platform=platform, server=login_data.server, login=login_data.login,
                broker_name=None, account_balance=0.0, account_equity=0.0,
                account_currency="USD", detected_symbols=[], supported_markets=[],
                warnings=[], metadata={},
            )

        from config.settings import USE_MOCK_TELEGRAM_SCAN as MOCK

        if MOCK:
            return self._mock_result(login_data)

        return await self._real_connect(login_data)

    # ------------------------------------------------------------------
    # Real connection via MT5Runtime
    # ------------------------------------------------------------------

    async def _real_connect(self, login_data: MTLoginData) -> MTAccountScanResult:
        from core_engine.mt_runtime import MTConnectionConfig, create_mt_runtime

        password = login_data.password
        config = MTConnectionConfig(
            server=login_data.server,
            login=login_data.login,
            password=password,
            platform=login_data.platform,
        )

        runtime = create_mt_runtime(config)
        if runtime is None:
            return MTAccountScanResult(
                success=False, state="RUNTIME_ERROR",
                message="Could not create MT runtime. Check that MetaTrader is installed.",
                platform=login_data.platform, server=login_data.server, login=login_data.login,
                broker_name=None, account_balance=0.0, account_equity=0.0,
                account_currency="USD", detected_symbols=[], supported_markets=[],
                warnings=["MT5 library not available"], metadata={},
            )

        try:
            async with asyncio.timeout(CONNECT_TIMEOUT_SECONDS):
                ok = await runtime.connect()
                if not ok:
                    return MTAccountScanResult(
                        success=False, state="CONNECTION_FAILED",
                        message="Connection failed. Check server, login and password.",
                        platform=login_data.platform, server=login_data.server, login=login_data.login,
                        broker_name=None, account_balance=0.0, account_equity=0.0,
                        account_currency="USD", detected_symbols=[], supported_markets=[],
                        warnings=[], metadata={},
                    )

                info = await runtime.account_info()
                symbols = await runtime.get_symbols()
                await runtime.disconnect()

        except asyncio.TimeoutError:
            logger.warning("MT connection timed out after %ss (login=%s)", CONNECT_TIMEOUT_SECONDS, login_data.login)
            return MTAccountScanResult(
                success=False, state="CONNECTION_TIMEOUT",
                message="Connection timed out. Check the server and try again.",
                platform=login_data.platform, server=login_data.server, login=login_data.login,
                broker_name=None, account_balance=0.0, account_equity=0.0,
                account_currency="USD", detected_symbols=[], supported_markets=[],
                warnings=[], metadata={},
            )
        except Exception as e:
            logger.exception("Real MT connection failed for %s", login_data.login)
            return MTAccountScanResult(
                success=False, state="CONNECTION_ERROR",
                message="Connection error. Please check your details and try again.",
                platform=login_data.platform, server=login_data.server, login=login_data.login,
                broker_name=None, account_balance=0.0, account_equity=0.0,
                account_currency="USD", detected_symbols=[], supported_markets=[],
                warnings=[], metadata={},
            )

        if info is None:
            return MTAccountScanResult(
                success=False, state="NO_ACCOUNT_INFO",
                message="Connected but could not retrieve account info.",
                platform=login_data.platform, server=login_data.server, login=login_data.login,
                broker_name=None, account_balance=0.0, account_equity=0.0,
                account_currency="USD", detected_symbols=[], supported_markets=[],
                warnings=[], metadata={},
            )

        broker_name = self._detect_broker(login_data.server, info.company)
        sym_names = sorted({s.name for s in symbols}) if symbols else []

        return MTAccountScanResult(
            success=True,
            state="CONNECTED",
            message="Account connected successfully.",
            platform=login_data.platform,
            server=login_data.server,
            login=login_data.login,
            broker_name=broker_name or info.company or "Unknown",
            account_balance=info.balance or 0.0,
            account_equity=info.equity or 0.0,
            account_currency=info.currency or "USD",
            detected_symbols=sym_names,
            supported_markets=self._infer_markets(sym_names),
            leverage=f"1:{info.leverage}",
            trade_mode="REAL" if not info.is_demo else "DEMO",
            company=info.company or "",
            hedge_mode="",
            timezone="",
            build=0,
            warnings=[],
            metadata={"mock": False, "account_name": info.name or "", "is_demo": info.is_demo},
        )

    # ------------------------------------------------------------------
    # Mock
    # ------------------------------------------------------------------

    def _mock_result(self, login_data: MTLoginData) -> MTAccountScanResult:
        detected_symbols = ["XAUUSD", "NAS100", "BTCUSD"]
        return MTAccountScanResult(
            success=True, state="CONNECTED",
            message="Account connected successfully.",
            platform=login_data.platform, server=login_data.server, login=login_data.login,
            broker_name="Mock Broker",
            account_balance=10000.0, account_equity=10000.0,
            account_currency="USD",
            detected_symbols=detected_symbols,
            supported_markets=["GOLD", "NASDAQ", "BTC"],
            leverage="1:100", trade_mode="DEMO",
            warnings=[], metadata={"mock": True, "note": "Real MT4/MT5 bridge will replace this mock connector."},
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    BROKER_SERVER_MAP = {
        "FTMO": "FTMO", "FUNDINGPIPS": "FundingPips", "FUNDEDNEXT": "FundedNext",
        "THE5ERS": "The5ers", "ICMARKETS": "IC Markets", "PEPPERSTONE": "Pepperstone",
        "EXNESS": "Exness", "XM": "XM", "OANDA": "OANDA", "FOREX": "Forex.com",
        "EIGHT": "Eightcap", "BLUE": "Blueberry Markets", "FP": "FP Markets",
        "VANTAGE": "Vantage", "TICKMILL": "Tickmill", "HOTFOREX": "HotForex",
        "FBS": "FBS", "ROBO": "RoboForex", "JUST": "JustMarkets",
    }

    def _detect_broker(self, server: str, company: str) -> Optional[str]:
        combined = (server + " " + company).upper()
        for key, name in self.BROKER_SERVER_MAP.items():
            if key in combined:
                return name
        if server:
            base = server.split("-")[0].split(".")[0].strip()
            for key, name in self.BROKER_SERVER_MAP.items():
                if key in base.upper():
                    return name
        return None

    def _infer_markets(self, symbols: List[str]) -> List[str]:
        markets = []
        upper = {s.upper() for s in symbols}
        if any(s in upper for s in ("XAUUSD", "GOLD", "XAUUSD.a", "XAUUSD.c")):
            markets.append("GOLD")
        if any(s in upper for s in ("NAS100", "US100", "USTEC", "NAS100.a")):
            markets.append("NASDAQ")
        if any(s in upper for s in ("BTCUSD", "BTCUSDT", "XBTUSD")):
            markets.append("BTC")
        return markets


mt_connector = MTConnector()

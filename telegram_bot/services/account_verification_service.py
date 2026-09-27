from dataclasses import dataclass, field
from typing import Any, List, Optional

from database.db import async_session_factory
from database.repositories import AccountRepository
from telegram_bot.data.prop_firms import get_prop_program

MARKET_NAMES = {
    "GOLD": {"EN": "Gold", "FR": "Or", "AR": "ذهب", "ES": "Oro"},
    "NASDAQ": {"EN": "Nasdaq", "FR": "Nasdaq", "AR": "ناسداك", "ES": "Nasdaq"},
    "BITCOIN": {"EN": "Bitcoin", "FR": "Bitcoin", "AR": "بيتكوين", "ES": "Bitcoin"},
}

RISK_LABELS = {"EN": "Risk", "FR": "Risque", "AR": "المخاطرة", "ES": "Riesgo"}

# Server-name → broker-name mapping (for auto-detection when real MT5 connects)
BROKER_SERVER_MAP = {
    "FTMO": "FTMO",
    "FUNDINGPIPS": "FundingPips",
    "FUNDEDNEXT": "FundedNext",
    "THE5ERS": "The5ers",
    "ICMARKETS": "IC Markets",
    "PEPPERSTONE": "Pepperstone",
    "EXNESS": "Exness",
    "XM": "XM",
    "OANDA": "OANDA",
    "FOREX": "Forex.com",
    "EIGHT": "Eightcap",
    "BLUE": "Blueberry Markets",
    "FP": "FP Markets",
    "VANTAGE": "Vantage",
    "TICKMILL": "Tickmill",
    "HOTFOREX": "HotForex",
    "FBS": "FBS",
    "ROBO": "RoboForex",
    "JUST": "JustMarkets",
}


STANDARD_SIZES = [2000, 5000, 10000, 25000, 50000, 100000, 200000]


def normalize_account_size(balance: float) -> str:
    nearest = min(STANDARD_SIZES, key=lambda x: abs(x - balance))
    if nearest >= 1000000:
        return f"{nearest // 1000000}M"
    return f"{nearest // 1000}K"


def _fmt(n: float) -> str:
    if n >= 1000000:
        return f"{n / 1000000:g}M"
    if n >= 1000:
        return f"{n / 1000:g}K"
    return f"{n:g}"


def _parse_balance(raw: Any) -> Optional[float]:
    if raw is None:
        return None
    s = str(raw).strip().upper().replace(" ", "")
    try:
        if s.endswith("K"):
            return float(s[:-1]) * 1000
        if s.endswith("M"):
            return float(s[:-1]) * 1000000
        return float(s)
    except Exception:
        return None


def detect_account_environment(server: str, is_demo: Optional[bool] = None, trade_mode: str = "") -> str:
    server_lower = (server or "").lower()
    if "demo" in server_lower or "trial" in server_lower:
        return "DEMO"
    if is_demo is True:
        return "DEMO"
    if is_demo is False:
        return "REAL"
    if trade_mode.upper() == "DEMO":
        return "DEMO"
    if trade_mode.upper() == "REAL":
        return "REAL"
    return "UNKNOWN"


# ----------------------------------------------------------------
# Phase 1 — Connection
# ----------------------------------------------------------------
@dataclass
class ConnectionResult:
    success: bool
    error_type: Optional[str] = None
    error_message: Optional[str] = None


# ----------------------------------------------------------------
# Phase 2 — Account Info
# ----------------------------------------------------------------
@dataclass
class AccountInfo:
    name: str = ""
    login: str = ""
    server: str = ""
    broker: str = ""
    company: str = ""
    balance: float = 0.0
    equity: float = 0.0
    margin: float = 0.0
    leverage: str = ""
    currency: str = "USD"
    trade_mode: str = ""        # DEMO / REAL
    hedge_mode: str = ""        # HEDGE / NETTING
    platform: str = ""
    timezone: str = ""
    build: int = 0


# ----------------------------------------------------------------
# Phase 3 — Market Scan
# ----------------------------------------------------------------
@dataclass
class MarketEntry:
    market: str
    found: bool
    broker_symbol: Optional[str] = None


# ----------------------------------------------------------------
# Phase 4 — Comparison
# ----------------------------------------------------------------
@dataclass
class ValidationItem:
    field: str
    label: str
    status: str              # "match" | "warning" | "error"
    expected: str = ""
    actual: str = ""


@dataclass
class ComparisonResult:
    items: List[ValidationItem] = field(default_factory=list)

    @property
    def has_warnings(self) -> bool:
        return any(i.status == "warning" for i in self.items)

    @property
    def has_errors(self) -> bool:
        return any(i.status == "error" for i in self.items)

    @property
    def all_match(self) -> bool:
        return all(i.status == "match" for i in self.items) if self.items else True


# ----------------------------------------------------------------
# Phase 5 — Risk
# ----------------------------------------------------------------
@dataclass
class RiskAssessment:
    daily_loss_pct: Optional[float] = None
    max_loss_pct: Optional[float] = None
    remaining_daily_pct: Optional[float] = None
    remaining_max_pct: Optional[float] = None
    current_daily_dd_pct: Optional[float] = None
    current_total_dd_pct: Optional[float] = None
    warnings: List[str] = field(default_factory=list)


# ----------------------------------------------------------------
# Phase 6 — Final Report
# ----------------------------------------------------------------
@dataclass
class ScanReport:
    connection: ConnectionResult
    account: Optional[AccountInfo] = None
    markets: List[MarketEntry] = field(default_factory=list)
    comparison: Optional[ComparisonResult] = None
    risk: Optional[RiskAssessment] = None


# ================================================================
# Account Scanner
# ================================================================
class AccountScanner:

    # ------------------------------------------------------------
    # Phase 1 — Connect
    # ------------------------------------------------------------
    async def connect(self, login_data) -> ConnectionResult:
        platform = str(getattr(login_data, "platform", "")).upper().strip()

        if platform != "MT5":
            return ConnectionResult(
                success=False,
                error_type="UNSUPPORTED_PLATFORM",
                error_message="Unsupported platform. Only MT5 is supported.",
            )

        from config.settings import USE_MOCK_TELEGRAM_SCAN as MOCK

        if MOCK:
            return ConnectionResult(success=True)

        return await self._real_connect(login_data)

    async def _real_connect(self, login_data) -> ConnectionResult:
        from core_engine.mt_runtime import MTConnectionConfig, create_mt_runtime

        config = MTConnectionConfig(
            server=login_data.server,
            login=login_data.login,
            password=login_data.password,
            platform=login_data.platform,
        )
        runtime = create_mt_runtime(config)
        if runtime is None:
            return ConnectionResult(
                success=False, error_type="RUNTIME_ERROR",
                error_message="Could not create MT runtime.",
            )
        try:
            ok = await runtime.connect()
            if not ok:
                return ConnectionResult(
                    success=False, error_type="CONNECTION_FAILED",
                    error_message="Connection failed. Check server, login and password.",
                )
            await runtime.disconnect()
            return ConnectionResult(success=True)
        except Exception as e:
            return ConnectionResult(
                success=False, error_type="CONNECTION_ERROR",
                error_message=str(e),
            )

    # ------------------------------------------------------------
    # Phase 2 — Scan Account Info
    # ------------------------------------------------------------
    def scan_account(self, login_data, setup_data: dict = None,
                     scan_result=None) -> AccountInfo:
        platform = str(getattr(login_data, "platform", "MT5")).upper()
        server = getattr(login_data, "server", "")
        login = getattr(login_data, "login", "")

        from config.settings import USE_MOCK_TELEGRAM_SCAN as MOCK

        if not MOCK and scan_result and scan_result.success:
            balance = scan_result.account_balance
            equity = scan_result.account_equity

            if balance is None:
                raise ValueError("MT5 did not return account balance")

            is_demo = getattr(scan_result, "is_demo", None)
            if is_demo is None and hasattr(scan_result, "metadata"):
                is_demo = scan_result.metadata.get("is_demo")

            trade_mode = detect_account_environment(server, is_demo=is_demo, trade_mode=scan_result.trade_mode)

            name = scan_result.metadata.get("account_name", "") if scan_result.metadata else ""
            if not name:
                name = f"Account {login}"

            return AccountInfo(
                name=name,
                login=login,
                server=server,
                broker=scan_result.broker_name or "",
                company=scan_result.company or "",
                balance=balance,
                equity=equity or 0.0,
                margin=0.0,
                leverage=scan_result.leverage or "1:100",
                currency=scan_result.account_currency or "USD",
                trade_mode=trade_mode,
                hedge_mode=scan_result.hedge_mode or "",
                platform=platform,
                timezone=scan_result.timezone or "",
                build=scan_result.build or 0,
            )

        broker_name = (
            (setup_data or {}).get("prop_firm", {}).get("name")
            or (setup_data or {}).get("broker", {}).get("name")
            or "Unknown Broker"
        )
        company_name = (
            (setup_data or {}).get("prop_firm", {}).get("name")
            or (setup_data or {}).get("broker", {}).get("name")
            or "Unknown Ltd"
        )

        return AccountInfo(
            name="Mock Trader",
            login=login,
            server=server,
            broker=broker_name,
            company=company_name,
            balance=10000.0,
            equity=10000.0,
            margin=0.0,
            leverage="1:100",
            currency="USD",
            trade_mode="DEMO",
            hedge_mode="HEDGE",
            platform=platform,
            timezone="UTC+2",
            build=4500,
        )

    # ------------------------------------------------------------
    # Phase 3 — Market Scan
    # ------------------------------------------------------------
    def scan_markets(self, symbols_raw) -> List[MarketEntry]:
        from core_engine.data_feed.symbol_resolver import resolve_required_markets

        symbols_list = symbols_raw if isinstance(symbols_raw, list) else []
        resolved = resolve_required_markets(symbols_list)

        entries: List[MarketEntry] = []
        for market in ("GOLD", "NASDAQ", "BITCOIN"):
            rs = resolved.get(market)
            entries.append(MarketEntry(
                market=market,
                found=rs is not None and rs.symbol is not None,
                broker_symbol=rs.symbol if rs else None,
            ))

        return entries

    # ------------------------------------------------------------
    # Broker auto-detection (server/company → known broker)
    # ------------------------------------------------------------
    def detect_broker(self, server: str, company: str) -> Optional[str]:
        combined = (server + " " + company).upper()
        for key, name in BROKER_SERVER_MAP.items():
            if key in combined:
                return name
        # Fallback: try the first word of the server before "-" or " "
        if server:
            base = server.split("-")[0].split(".")[0].strip()
            for key, name in BROKER_SERVER_MAP.items():
                if key in base.upper():
                    return name
        return None

    # ------------------------------------------------------------
    # Phase 4 — Compare with client data
    # ------------------------------------------------------------
    def compare(self, account: AccountInfo, setup_data: dict, user_data: dict) -> ComparisonResult:
        items: List[ValidationItem] = []
        is_funded = setup_data.get("account", {}).get("type") == "FUNDED"

        user_balance_raw = user_data.get("account_balance") or user_data.get("funded_account_size")
        user_balance = _parse_balance(user_balance_raw)

        # --- Broker match ---
        configured_broker = (
            setup_data.get("prop_firm", {}).get("name")
            or setup_data.get("broker", {}).get("name")
            or ""
        ).strip()
        detected_broker = account.broker.strip()
        if configured_broker and detected_broker:
            if configured_broker.upper() == detected_broker.upper():
                items.append(ValidationItem("broker", "Broker", "match", detected_broker, configured_broker))
            else:
                items.append(ValidationItem("broker", "Broker", "warning", detected_broker, configured_broker))

        # --- Platform match ---
        configured_platform = setup_data.get("platform", {}).get("platform", "").upper()
        detected_platform = account.platform.upper()
        if configured_platform and detected_platform:
            if configured_platform == detected_platform:
                items.append(ValidationItem("platform", "Platform", "match", detected_platform, configured_platform))
            else:
                items.append(ValidationItem("platform", "Platform", "error", detected_platform, configured_platform))

        # --- Balance ---
        if user_balance and account.balance:
            diff = abs(account.balance - user_balance) / user_balance * 100
            detected_size = normalize_account_size(account.balance)
            configured_size = normalize_account_size(user_balance)
            if diff <= 20:
                items.append(ValidationItem("balance", "Account Size", "match", configured_size, detected_size))
            else:
                items.append(ValidationItem("balance", "Account Size", "warning", configured_size, detected_size))

        # --- Trade mode (Demo / Real) ---
        if is_funded:
            expected_type = "Real"
            detected_type = account.trade_mode.upper() if account.trade_mode else "UNKNOWN"
            if detected_type == expected_type.upper():
                items.append(ValidationItem("trade_mode", "Account Type", "match", expected_type, detected_type))
            else:
                items.append(ValidationItem("trade_mode", "Account Type", "warning", expected_type, detected_type))
        else:
            detected_type = account.trade_mode.upper() if account.trade_mode else "UNKNOWN"
            items.append(ValidationItem("trade_mode", "Account Type", "match", detected_type, detected_type))

        return ComparisonResult(items=items)

    # ------------------------------------------------------------
    # Phase 5 — Risk Assessment
    # ------------------------------------------------------------
    def assess_risk(self, account: AccountInfo, setup_data: dict, stored_daily_loss_pct: Optional[float] = None, stored_max_loss_pct: Optional[float] = None, stored_daily_dd_pct: Optional[float] = None, stored_total_dd_pct: Optional[float] = None) -> RiskAssessment:
        balance = account.balance
        equity = account.equity
        risk = setup_data.get("risk", {})

        daily_loss_pct = risk.get("daily_loss")
        max_loss_pct = risk.get("max_loss")
        prop_id = setup_data.get("prop_firm", {}).get("id")
        program_id = setup_data.get("prop_firm", {}).get("program_id")

        if daily_loss_pct is None and prop_id and program_id:
            prog = get_prop_program(prop_id, program_id)
            if prog:
                daily_loss_pct = prog["rules"].get("daily_loss")
                max_loss_pct = prog["rules"].get("max_loss")

        assessment = RiskAssessment(
            daily_loss_pct=daily_loss_pct,
            max_loss_pct=max_loss_pct,
        )

        current_dd_val = max(0, balance - equity)
        current_dd_pct = (current_dd_val / balance * 100) if balance > 0 else 0

        if max_loss_pct and balance > 0:
            if stored_total_dd_pct is not None:
                assessment.current_total_dd_pct = stored_total_dd_pct
                remaining_max_pct = max(0.0, max_loss_pct - stored_total_dd_pct)
            else:
                max_loss_amount = balance * max_loss_pct / 100
                remaining_max = max_loss_amount - current_dd_val
                remaining_max_pct = (remaining_max / balance) * 100 if balance > 0 else 0
                assessment.current_total_dd_pct = current_dd_pct
            assessment.remaining_max_pct = max(0, remaining_max_pct)
            if remaining_max_pct < max_loss_pct * 0.3:
                assessment.warnings.append(
                    f"Remaining Max Loss: {remaining_max_pct:.1f}%\n"
                    "⚠ Be careful."
                )

        if daily_loss_pct and balance > 0:
                if stored_daily_dd_pct is not None:
                    assessment.current_daily_dd_pct = stored_daily_dd_pct
                    remaining_daily_pct = max(0.0, daily_loss_pct - stored_daily_dd_pct)
                else:
                    daily_loss_amount = balance * daily_loss_pct / 100
                    remaining_daily = max(0, daily_loss_amount - current_dd_val)
                    remaining_daily_pct = (remaining_daily / balance) * 100 if balance > 0 else 0
                    assessment.current_daily_dd_pct = current_dd_pct
                assessment.remaining_daily_pct = remaining_daily_pct

        return assessment

    # ------------------------------------------------------------
    # Full run
    # ------------------------------------------------------------
    async def run_full_scan(
        self,
        login_data,
        scan_result,
        setup_data: dict,
        user_data: dict,
        account_id: Optional[str] = None,
    ) -> ScanReport:
        if not scan_result or not scan_result.success:
            return ScanReport(
                connection=ConnectionResult(
                    success=False,
                    error_type="SCAN_FAILED",
                    error_message=getattr(scan_result, "message", "Connection test failed"),
                )
            )

        account = self.scan_account(login_data, setup_data, scan_result=scan_result)
        markets = self.scan_markets(
            getattr(scan_result, "detected_symbols", [])
        )
        comparison = self.compare(account, setup_data, user_data)

        stored_daily_dd = None
        stored_total_dd = None
        if account_id:
            async with async_session_factory() as session:
                repo = AccountRepository(session)
                db_account = await repo.get_by_id(account_id)
                if db_account and db_account.risk_profile:
                    stored_daily_dd = db_account.risk_profile.current_daily_loss_pct
                    stored_total_dd = db_account.risk_profile.current_max_loss_pct

        risk = self.assess_risk(account, setup_data, stored_daily_dd_pct=stored_daily_dd, stored_total_dd_pct=stored_total_dd)

        return ScanReport(
            connection=ConnectionResult(success=True),
            account=account,
            markets=markets,
            comparison=comparison,
            risk=risk,
        )

    # ------------------------------------------------------------
    # Format report as Telegram message
    # ------------------------------------------------------------
    def format_report(self, report: ScanReport, setup_data: dict, lang: str) -> List[str]:
        messages: List[str] = []
        account = report.account

        if not report.connection.success:
            messages.append("❌ <b>Connection Error</b>\n\nReason:\n" + (report.connection.error_message or "Unknown error"))
            return messages

        if not account:
            return messages

        account_type = setup_data.get("account", {}).get("type", "").upper()
        is_funded = account_type == "FUNDED"
        is_personal = account_type == "PERSONAL"

        program_name = setup_data.get("prop_firm", {}).get("program_name", "")
        program_challenge = setup_data.get("prop_firm", {}).get("challenge_type", "")
        account_type_str = setup_data.get("prop_firm", {}).get("account_type", "")
        balance_raw = setup_data.get("account", {}).get("balance") or account.balance

        server = setup_data.get("platform", {}).get("server") or account.server
        r = report.risk

        def nn(val, default="—"):
            return val if val else default

        # ------------------------------------------------------------------
        # Section 1 — Detected
        # ------------------------------------------------------------------
        D = {
            "EN": {"t": "Detected", "br": "Broker", "co": "Company", "sv": "Server", "pl": "Platform", "ba": "Balance", "eq": "Equity", "lv": "Leverage", "cu": "Currency", "ty": "Account Type", "mo": "Trade Mode", "r": "Real", "d": "Demo", "h": "Hedging", "n": "Netting", "tz": "Timezone", "bl": "Build"},
            "FR": {"t": "Détecté", "br": "Courtier", "co": "Société", "sv": "Serveur", "pl": "Plateforme", "ba": "Solde", "eq": "Capitaux", "lv": "Levier", "cu": "Devise", "ty": "Type", "mo": "Mode", "r": "Réel", "d": "Démo", "h": "Hedging", "n": "Netting", "tz": "Fuseau", "bl": "Build"},
            "AR": {"t": "المكتشف", "br": "الوسيط", "co": "الشركة", "sv": "السيرفر", "pl": "المنصة", "ba": "الرصيد", "eq": "الحقوق", "lv": "الرافعة", "cu": "العملة", "ty": "نوع الحساب", "mo": "النمط", "r": "حقيقي", "d": "تجريبي", "h": "مقاصة", "n": "صافي", "tz": "التوقيت", "bl": "الإصدار"},
            "ES": {"t": "Detectado", "br": "Broker", "co": "Compañía", "sv": "Servidor", "pl": "Plataforma", "ba": "Saldo", "eq": "Fondos", "lv": "Apalancamiento", "cu": "Divisa", "ty": "Tipo", "mo": "Modo", "r": "Real", "d": "Demo", "h": "Hedging", "n": "Netting", "tz": "Zona horaria", "bl": "Build"},
        }.get(lang)
        mode_str = D["h"] if account.hedge_mode == "HEDGE" else D["n"]
        type_str = D["r"] if account.trade_mode == "REAL" else D["d"]

        det = [
            f"<b>{D['t']}</b>",
            "",
            f"<b>{D['br']}:</b> {nn(account.broker)}",
            f"<b>{D['co']}:</b> {nn(account.company)}",
            f"<b>{D['sv']}:</b> {nn(server)}",
            f"<b>{D['pl']}:</b> {nn(account.platform)}",
            f"<b>{D['ba']}:</b> {normalize_account_size(account.balance)} {account.currency}",
            f"<b>{D['eq']}:</b> {_fmt(account.equity)} {account.currency}",
            f"<b>{D['lv']}:</b> {nn(account.leverage)}",
            f"<b>{D['cu']}:</b> {nn(account.currency)}",
            f"<b>{D['ty']}:</b> {type_str}",
            f"<b>{D['mo']}:</b> {mode_str}",
        ]
        for m in report.markets:
            icon = "✅" if m.found else "❌"
            sym = m.broker_symbol or m.market
            name = MARKET_NAMES.get(m.market, {}).get(lang, m.market)
            det.append(f"<b>{name}:</b> {icon} {sym}")
        det.append(f"<b>{D['tz']}:</b> {nn(account.timezone)}")
        det.append(f"<b>{D['bl']}:</b> {nn(str(account.build)) if account.build else '—'}")
        messages.append("\n".join(det))

        # ------------------------------------------------------------------
        # Section 2 — Configured
        # ------------------------------------------------------------------
        if is_funded:
            C = {
                "EN": {"t": "Configured", "firm": "Firm", "challenge": "Challenge", "type": "Type", "size": "Size", "daily": "Daily Loss Limit", "max": "Max Loss Limit"},
                "FR": {"t": "Configuré", "firm": "Firme", "challenge": "Défi", "type": "Type", "size": "Taille", "daily": "Limite perte quotidienne", "max": "Limite perte max"},
                "AR": {"t": "الإعدادات", "firm": "الشركة", "challenge": "التحدي", "type": "النوع", "size": "الحجم", "daily": "حد الخسارة اليومية", "max": "حد الخسارة القصوى"},
                "ES": {"t": "Configurado", "firm": "Firma", "challenge": "Desafío", "type": "Tipo", "size": "Tamaño", "daily": "Límite pérdida diaria", "max": "Límite pérdida máxima"},
            }.get(lang)
            step_info = ""
            if account.name:
                upper = account.name.upper()
                if "1-STEP" in upper or "1STEP" in upper:
                    step_info = "1-Step"
                elif "2-STEP" in upper or "2STEP" in upper:
                    step_info = "2-Step"

            cfg = [f"<b>{C['t']}</b>", ""]
            firm_name = setup_data.get("prop_firm", {}).get("name") or account.broker
            cfg.append(f"<b>{C['firm']}:</b> {firm_name}")
            if program_name:
                step_part = f" ({step_info})" if step_info else ""
                cfg.append(f"<b>{C['challenge']}:</b> {program_name}{step_part}")
            elif step_info:
                cfg.append(f"<b>{C['challenge']}:</b> {step_info}")
            if account_type_str:
                cfg.append(f"<b>{C['type']}:</b> {account_type_str}")
            cfg.append(f"<b>{C['size']}:</b> {normalize_account_size(account.balance)} {account.currency}")
            cfg.append(f"\n<em>Source: configured by user</em>")
            if r:
                if r.daily_loss_pct is not None:
                    cfg.append(f"<b>{C['daily']}:</b> {r.daily_loss_pct:.0f}%")
                if r.max_loss_pct is not None:
                    cfg.append(f"<b>{C['max']}:</b> {r.max_loss_pct:.0f}%")
            messages.append("\n".join(cfg))
        elif is_personal:
            C = {"EN": {"t": "Configured", "br": "Broker", "size": "Size"}, "FR": {"t": "Configuré", "br": "Courtier", "size": "Taille"}, "AR": {"t": "الإعدادات", "br": "الوسيط", "size": "الحجم"}, "ES": {"t": "Configurado", "br": "Broker", "size": "Tamaño"}}.get(lang)
            bn = setup_data.get("broker", {}).get("name") or account.broker
            messages.append("\n".join([f"<b>{C['t']}</b>", "", f"<b>{C['br']}:</b> {bn}", f"<b>{C['size']}:</b> {normalize_account_size(account.balance)} {account.currency}"]))
        else:
            C = {"EN": {"t": "Configured", "src": "Source", "size": "Size"}, "FR": {"t": "Configuré", "src": "Source", "size": "Taille"}, "AR": {"t": "الإعدادات", "src": "المصدر", "size": "الحجم"}, "ES": {"t": "Configurado", "src": "Fuente", "size": "Tamaño"}}.get(lang)
            bn = setup_data.get("broker", {}).get("name") or account.broker
            messages.append("\n".join([f"<b>{C['t']}</b>", "", f"<b>{C['src']}:</b> {bn}", f"<b>{C['size']}:</b> {normalize_account_size(account.balance)} {account.currency}"]))

        # ------------------------------------------------------------------
        # Section 3 — Validation (smart)
        # ------------------------------------------------------------------
        val_title = {"EN": "Validation", "FR": "Validation", "AR": "التحقق", "ES": "Validación"}.get(lang)
        val_lines = [f"<b>{val_title}</b>"]

        if report.comparison and report.comparison.items:
            for v in report.comparison.items:
                if v.status == "match":
                    val_lines.append(f"\n✅ <b>{v.label} Match</b>")
                elif v.status == "warning":
                    val_lines.append(f"\n🟡 <b>{v.label} Mismatch</b>")
                    if v.expected or v.actual:
                        val_lines.append(f"  Configured: {v.expected}")
                        val_lines.append(f"  Detected:   {v.actual}")
                elif v.status == "error":
                    val_lines.append(f"\n❌ <b>{v.label} Error</b>")
                    if v.expected or v.actual:
                        val_lines.append(f"  Configured: {v.expected}")
                        val_lines.append(f"  Detected:   {v.actual}")
        else:
            val_lines.append(f"\n{'- No checks performed -'}")

        messages.append("".join(val_lines))

        # ------------------------------------------------------------------
        # Section 4 — Risk Status
        # ------------------------------------------------------------------
        if r:
            risk_title = {"EN": "Risk Status", "FR": "État des risques", "AR": "حالة المخاطرة", "ES": "Estado de riesgo"}.get(lang)
            Rl = {"EN": {"limit": "Limit", "curr": "Current", "rem": "Remaining"}, "FR": {"limit": "Limite", "curr": "Actuel", "rem": "Restant"}, "AR": {"limit": "الحد", "curr": "الحالي", "rem": "المتبقي"}, "ES": {"limit": "Límite", "curr": "Actual", "rem": "Restante"}}.get(lang)

            rx = [f"<b>{risk_title}</b>"]

            if is_funded:
                if r.daily_loss_pct is not None and r.remaining_daily_pct is not None:
                    rx.append(
                        f"\n<b>Daily Loss</b>\n"
                        f"  {Rl['limit']}: {r.daily_loss_pct:.0f}%\n"
                        f"  {Rl['curr']}: {r.current_daily_dd_pct or 0:.1f}%\n"
                        f"  {Rl['rem']}: {r.remaining_daily_pct:.1f}%"
                    )
                if r.max_loss_pct is not None and r.remaining_max_pct is not None:
                    rx.append(
                        f"\n<b>Max Loss</b>\n"
                        f"  {Rl['limit']}: {r.max_loss_pct:.0f}%\n"
                        f"  {Rl['curr']}: {r.current_total_dd_pct or 0:.1f}%\n"
                        f"  {Rl['rem']}: {r.remaining_max_pct:.1f}%"
                    )
            else:
                dd_pct = (max(0, account.balance - account.equity) / account.balance * 100) if account.balance > 0 else 0
                dd_tag = {"EN": "Drawdown", "FR": "Drawdown", "AR": "السحب", "ES": "Drawdown"}.get(lang)
                rx.append(f"\n<b>{dd_tag}:</b> {dd_pct:.1f}%")

            for w in r.warnings:
                rx.append(f"\n{w}")
            messages.append("\n".join(rx))

        # ------------------------------------------------------------------
        # Section 5 — System Check (pre-flight)
        # ------------------------------------------------------------------
        sys_title = {"EN": "System Check", "FR": "Vérification système", "AR": "فحص النظام", "ES": "Verificación del sistema"}.get(lang)
        sys = [f"\n<b>{sys_title}</b>"]

        # Connection
        conn_ok = report.connection.success
        sys.append(f"\n{'✅' if conn_ok else '❌'} <b>Connection</b>")

        # Symbols
        if report.markets:
            all_found = all(m.found for m in report.markets)
            sys.append(f"\n{'✅' if all_found else '❌'} <b>Symbols</b>")

        # Broker
        if report.comparison and report.comparison.items:
            broker_item = next((i for i in report.comparison.items if i.field == "broker"), None)
            if broker_item:
                sys.append(f"\n{'✅' if broker_item.status == 'match' else '🟡'} <b>Broker</b>")

        # Rules (funded only)
        if is_funded:
            has_rules = r and (r.daily_loss_pct is not None or r.max_loss_pct is not None)
            sys.append(f"\n{'✅' if has_rules else '❌'} <b>Rules</b>")

        # Account Type warning
        if report.comparison:
            type_item = next((i for i in report.comparison.items if i.field == "trade_mode"), None)
            if type_item and type_item.status == "warning":
                sys.append(f"\n🟡 <b>Demo Account</b>")

        sys.append(f"\n—\n{'Ready for activation.' if lang in ('EN', 'FR', 'ES') else 'جاهز للتفعيل.'}")
        messages.append("\n".join(sys))

        return messages


account_scanner = AccountScanner()

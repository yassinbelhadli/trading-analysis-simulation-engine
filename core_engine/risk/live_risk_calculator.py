"""
LiveRiskCalculator — single source of truth for account risk state.

Calculates all risk metrics from authoritative data:
- balance_snapshot (from scanner)
- equity_snapshot (from scanner)
- RiskProfile (from DB)
- open positions (from paper_trades / runtime)

Returns a structured RiskStatus with all metrics.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone


class RiskLevel(str, Enum):
    SAFE = "SAFE"
    REDUCED = "REDUCED"
    BLOCKED = "BLOCKED"
    UNVERIFIED = "UNVERIFIED"
    UNKNOWN = "UNKNOWN"


@dataclass
class OpenPosition:
    """Summary of an open position for risk calculation."""
    id: str
    symbol: str
    direction: str  # BUY / SELL
    entry_price: float
    lot_size: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    unrealized_pnl: float = 0.0


@dataclass
class RiskStatus:
    """Complete risk state for an account — single source of truth."""

    # ── Account basics ──
    account_id: str
    account_type: str  # PERSONAL / CHALLENGE / FUNDED / UNKNOWN
    risk_level: RiskLevel
    risk_level_message: str

    # ── Balance / Equity ──
    balance: float = 0.0
    equity: float = 0.0
    currency: str = "USD"

    # ── P&L ──
    floating_pnl: float = 0.0
    today_realized_pnl: float = 0.0
    today_floating_pnl: float = 0.0

    # ── Drawdown ──
    initial_balance: float = 0.0
    high_water_mark: float = 0.0
    current_drawdown_pct: float = 0.0
    current_drawdown_usd: float = 0.0
    drawdown_type: str = "static"  # static / trailing

    # ── Daily loss ──
    daily_loss_limit_pct: float = 0.0
    daily_loss_limit_usd: float = 0.0
    current_daily_loss_usd: float = 0.0
    remaining_daily_loss_usd: float = 0.0
    remaining_daily_loss_pct: float = 0.0

    # ── Max loss ──
    max_loss_limit_pct: float = 0.0
    max_loss_limit_usd: float = 0.0
    total_realized_loss_usd: float = 0.0
    remaining_max_loss_usd: float = 0.0
    remaining_max_loss_pct: float = 0.0

    # ── Open risk ──
    open_positions_count: int = 0
    total_open_risk_usd: float = 0.0
    current_open_risk_usd: float = 0.0

    # ── Safety buffer ──
    safety_buffer_pct: float = 0.0
    safety_buffer_usd: float = 0.0

    # ── Proposed trade ──
    proposed_trade_risk_usd: float = 0.0
    projected_risk_after_trade_usd: float = 0.0
    distance_to_daily_violation_usd: float = 0.0
    distance_to_max_violation_usd: float = 0.0

    # ── Prop firm profile ──
    prop_firm: Optional[str] = None
    prop_firm_program: Optional[str] = None
    verification_status: str = "UNKNOWN"  # IDENTIFIED / VERIFIED_RULES / USER_PROVIDED_RULES / AMBIGUOUS / UNKNOWN

    # ── Trading mode ──
    trading_mode: str = "BALANCED"

    # ── Timestamps ──
    last_scan_at: Optional[str] = None
    last_risk_update: Optional[str] = None
    data_freshness: str = "FRESH"  # FRESH / STALE / UNKNOWN

    # ── Fail-closed flags ──
    risk_profile_missing: bool = False
    balance_stale: bool = False
    risk_calculation_failed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for API responses."""
        return {
            "account_id": self.account_id,
            "account_type": self.account_type,
            "risk_level": self.risk_level.value,
            "risk_level_message": self.risk_level_message,
            "balance": self.balance,
            "equity": self.equity,
            "currency": self.currency,
            "floating_pnl": self.floating_pnl,
            "today_realized_pnl": self.today_realized_pnl,
            "today_floating_pnl": self.today_floating_pnl,
            "initial_balance": self.initial_balance,
            "high_water_mark": self.high_water_mark,
            "current_drawdown_pct": self.current_drawdown_pct,
            "current_drawdown_usd": self.current_drawdown_usd,
            "drawdown_type": self.drawdown_type,
            "daily_loss_limit_pct": self.daily_loss_limit_pct,
            "daily_loss_limit_usd": self.daily_loss_limit_usd,
            "current_daily_loss_usd": self.current_daily_loss_usd,
            "remaining_daily_loss_usd": self.remaining_daily_loss_usd,
            "remaining_daily_loss_pct": self.remaining_daily_loss_pct,
            "max_loss_limit_pct": self.max_loss_limit_pct,
            "max_loss_limit_usd": self.max_loss_limit_usd,
            "total_realized_loss_usd": self.total_realized_loss_usd,
            "remaining_max_loss_usd": self.remaining_max_loss_usd,
            "remaining_max_loss_pct": self.remaining_max_loss_pct,
            "open_positions_count": self.open_positions_count,
            "total_open_risk_usd": self.total_open_risk_usd,
            "current_open_risk_usd": self.current_open_risk_usd,
            "safety_buffer_pct": self.safety_buffer_pct,
            "safety_buffer_usd": self.safety_buffer_usd,
            "proposed_trade_risk_usd": self.proposed_trade_risk_usd,
            "projected_risk_after_trade_usd": self.projected_risk_after_trade_usd,
            "distance_to_daily_violation_usd": self.distance_to_daily_violation_usd,
            "distance_to_max_violation_usd": self.distance_to_max_violation_usd,
            "prop_firm": self.prop_firm,
            "prop_firm_program": self.prop_firm_program,
            "verification_status": self.verification_status,
            "trading_mode": self.trading_mode,
            "last_scan_at": self.last_scan_at,
            "last_risk_update": self.last_risk_update,
            "data_freshness": self.data_freshness,
            "risk_profile_missing": self.risk_profile_missing,
            "balance_stale": self.balance_stale,
            "risk_calculation_failed": self.risk_calculation_failed,
        }


class LiveRiskCalculator:
    """
    Calculates live risk status from authoritative data sources.

    Usage:
        calc = LiveRiskCalculator()
        status = calc.calculate(
            account_id="...",
            account_type="FUNDED",
            balance=100000,
            equity=99500,
            risk_profile={...},
            open_positions=[...],
            today_realized_pnl=-200,
            today_floating_pnl=-500,
        )
    """

    # Safety buffer: never risk this percentage of account
    DEFAULT_SAFETY_BUFFER_PCT = 0.50  # 0.5% safety buffer

    # Staleness threshold: if last scan > 30 min, mark as stale
    STALE_THRESHOLD_SECONDS = 1800

    def calculate(
        self,
        account_id: str,
        account_type: str = "UNKNOWN",
        balance: float = 0.0,
        equity: float = 0.0,
        currency: str = "USD",
        risk_profile: Optional[Dict[str, Any]] = None,
        open_positions: Optional[List[OpenPosition]] = None,
        today_realized_pnl: float = 0.0,
        today_floating_pnl: float = 0.0,
        total_realized_loss_usd: float = 0.0,
        last_scan_at: Optional[str] = None,
        trading_mode: str = "BALANCED",
        prop_firm: Optional[str] = None,
        prop_firm_program: Optional[str] = None,
        verification_status: str = "UNKNOWN",
    ) -> RiskStatus:
        """
        Calculate complete risk status.

        If risk_profile is None → fail-closed (UNVERIFIED).
        If balance/equity are 0 → fail-closed (UNKNOWN).
        """
        now = datetime.now(timezone.utc).isoformat()
        open_positions = open_positions or []

        # ── Fail-closed checks ──
        if risk_profile is None:
            return RiskStatus(
                account_id=account_id,
                account_type=account_type,
                risk_level=RiskLevel.UNVERIFIED,
                risk_level_message="Risk profile not configured. Trading is blocked until a risk profile is set.",
                balance=balance,
                equity=equity,
                currency=currency,
                risk_profile_missing=True,
                verification_status=verification_status,
                trading_mode=trading_mode,
                last_scan_at=last_scan_at,
                last_risk_update=now,
                data_freshness="UNKNOWN",
            )

        if balance <= 0 and equity <= 0:
            return RiskStatus(
                account_id=account_id,
                account_type=account_type,
                risk_level=RiskLevel.UNKNOWN,
                risk_level_message="Account balance and equity are unknown. Trading is blocked.",
                risk_profile_missing=False,
                verification_status=verification_status,
                trading_mode=trading_mode,
                last_scan_at=last_scan_at,
                last_risk_update=now,
                data_freshness="UNKNOWN",
                risk_calculation_failed=True,
            )

        # ── Extract risk profile values ──
        initial_balance = risk_profile.get("initial_balance") or risk_profile.get("account_size") or balance
        day_start_balance = risk_profile.get("day_start_balance") or initial_balance
        day_start_equity = risk_profile.get("day_start_equity") or initial_balance
        # daily_high_equity is the trailing max equity (high water mark)
        high_water_mark = risk_profile.get("high_water_mark") or risk_profile.get("daily_high_equity") or initial_balance

        daily_loss_pct = risk_profile.get("daily_loss") or 3.0
        max_loss_pct = risk_profile.get("max_loss") or 10.0
        drawdown_type = risk_profile.get("drawdown_type") or "static"
        safety_buffer_pct = risk_profile.get("safety_buffer_pct") or self.DEFAULT_SAFETY_BUFFER_PCT

        # ── Use effective balance/equity ──
        eff_balance = balance if balance > 0 else initial_balance
        eff_equity = equity if equity > 0 else eff_balance

        # ── Drawdown ──
        current_drawdown_usd = max(0, initial_balance - eff_equity)
        current_drawdown_pct = (current_drawdown_usd / initial_balance * 100) if initial_balance > 0 else 0.0

        # Trailing drawdown uses high water mark
        if drawdown_type == "trailing" and high_water_mark > 0:
            trailing_dd_usd = max(0, high_water_mark - eff_equity)
            if trailing_dd_usd > current_drawdown_usd:
                current_drawdown_usd = trailing_dd_usd
                current_drawdown_pct = (trailing_dd_usd / high_water_mark * 100)

        # ── Daily loss ──
        daily_loss_limit_usd = day_start_balance * (daily_loss_pct / 100)
        current_daily_loss_usd = abs(min(0, today_realized_pnl)) + abs(min(0, today_floating_pnl))
        remaining_daily_loss_usd = max(0, daily_loss_limit_usd - current_daily_loss_usd)
        remaining_daily_loss_pct = (remaining_daily_loss_usd / day_start_balance * 100) if day_start_balance > 0 else 0.0

        # ── Max loss ──
        max_loss_limit_usd = initial_balance * (max_loss_pct / 100)
        remaining_max_loss_usd = max(0, max_loss_limit_usd - total_realized_loss_usd - current_drawdown_usd)
        remaining_max_loss_pct = (remaining_max_loss_usd / initial_balance * 100) if initial_balance > 0 else 0.0

        # ── Open risk ──
        total_open_risk = 0.0
        current_open_risk = 0.0
        for pos in open_positions:
            if pos.stop_loss and pos.lot_size > 0:
                # Calculate SL risk in USD
                sl_distance = abs(pos.entry_price - pos.stop_loss)
                # Approximate: for forex, 1 lot = 100,000 units; for gold, 1 lot = 100 oz
                # Simplified: use lot_size * sl_distance as risk proxy
                pos_risk = pos.lot_size * sl_distance
                total_open_risk += pos_risk
                current_open_risk += pos_risk

        # ── Safety buffer ──
        safety_buffer_usd = eff_balance * (safety_buffer_pct / 100)

        # ── Distance to violation ──
        distance_to_daily = remaining_daily_loss_usd
        distance_to_max = remaining_max_loss_usd

        # ── Floating P&L ──
        floating_pnl = eff_equity - eff_balance

        # ── Data freshness ──
        data_freshness = "FRESH"
        balance_stale = False
        if last_scan_at:
            try:
                scan_time = datetime.fromisoformat(last_scan_at.replace("Z", "+00:00"))
                age_seconds = (datetime.now(timezone.utc) - scan_time).total_seconds()
                if age_seconds > self.STALE_THRESHOLD_SECONDS:
                    data_freshness = "STALE"
                    balance_stale = True
            except (ValueError, TypeError):
                data_freshness = "UNKNOWN"

        # ── Risk level determination ──
        risk_level, risk_message = self._determine_risk_level(
            remaining_daily_loss_usd=remaining_daily_loss_usd,
            remaining_max_loss_usd=remaining_max_loss_usd,
            daily_loss_limit_usd=daily_loss_limit_usd,
            max_loss_limit_usd=max_loss_limit_usd,
            balance_stale=balance_stale,
            account_type=account_type,
        )

        return RiskStatus(
            account_id=account_id,
            account_type=account_type,
            risk_level=risk_level,
            risk_level_message=risk_message,
            balance=eff_balance,
            equity=eff_equity,
            currency=currency,
            floating_pnl=floating_pnl,
            today_realized_pnl=today_realized_pnl,
            today_floating_pnl=today_floating_pnl,
            initial_balance=initial_balance,
            high_water_mark=high_water_mark,
            current_drawdown_pct=round(current_drawdown_pct, 2),
            current_drawdown_usd=round(current_drawdown_usd, 2),
            drawdown_type=drawdown_type,
            daily_loss_limit_pct=round(daily_loss_pct, 2),
            daily_loss_limit_usd=round(daily_loss_limit_usd, 2),
            current_daily_loss_usd=round(current_daily_loss_usd, 2),
            remaining_daily_loss_usd=round(remaining_daily_loss_usd, 2),
            remaining_daily_loss_pct=round(remaining_daily_loss_pct, 2),
            max_loss_limit_pct=round(max_loss_pct, 2),
            max_loss_limit_usd=round(max_loss_limit_usd, 2),
            total_realized_loss_usd=round(total_realized_loss_usd, 2),
            remaining_max_loss_usd=round(remaining_max_loss_usd, 2),
            remaining_max_loss_pct=round(remaining_max_loss_pct, 2),
            open_positions_count=len(open_positions),
            total_open_risk_usd=round(total_open_risk, 2),
            current_open_risk_usd=round(current_open_risk, 2),
            safety_buffer_pct=round(safety_buffer_pct, 2),
            safety_buffer_usd=round(safety_buffer_usd, 2),
            proposed_trade_risk_usd=0.0,
            projected_risk_after_trade_usd=round(current_open_risk, 2),
            distance_to_daily_violation_usd=round(distance_to_daily, 2),
            distance_to_max_violation_usd=round(distance_to_max, 2),
            prop_firm=prop_firm,
            prop_firm_program=prop_firm_program,
            verification_status=verification_status,
            trading_mode=trading_mode,
            last_scan_at=last_scan_at,
            last_risk_update=now,
            data_freshness=data_freshness,
            risk_profile_missing=False,
            balance_stale=balance_stale,
            risk_calculation_failed=False,
        )

    def _determine_risk_level(
        self,
        remaining_daily_loss_usd: float,
        remaining_max_loss_usd: float,
        daily_loss_limit_usd: float,
        max_loss_limit_usd: float,
        balance_stale: bool,
        account_type: str,
    ) -> tuple[RiskLevel, str]:
        """Determine risk level with clear messaging."""

        # Stale data = fail-closed for automated trading
        if balance_stale:
            return RiskLevel.BLOCKED, "Account data is stale. Trading is blocked until fresh data is received."

        # Daily loss violation
        if daily_loss_limit_usd > 0 and remaining_daily_loss_usd <= 0:
            return RiskLevel.BLOCKED, f"Daily loss limit reached. No new trades allowed today."

        # Max loss violation
        if max_loss_limit_usd > 0 and remaining_max_loss_usd <= 0:
            return RiskLevel.BLOCKED, "Maximum loss limit reached. Trading is blocked."

        # Near daily limit (< 30% remaining)
        if daily_loss_limit_usd > 0:
            daily_remaining_pct = remaining_daily_loss_usd / daily_loss_limit_usd
            if daily_remaining_pct <= 0.30:
                return (
                    RiskLevel.REDUCED,
                    f"Daily loss limit approaching. Remaining: ${remaining_daily_loss_usd:,.0f} "
                    f"({daily_remaining_pct:.0%} of limit). Reduce position sizes."
                )

        # Near max limit (< 30% remaining)
        if max_loss_limit_usd > 0:
            max_remaining_pct = remaining_max_loss_usd / max_loss_limit_usd
            if max_remaining_pct <= 0.30:
                return (
                    RiskLevel.REDUCED,
                    f"Maximum loss limit approaching. Remaining: ${remaining_max_loss_usd:,.0f} "
                    f"({max_remaining_pct:.0%} of limit). Reduce position sizes."
                )

        # Safe
        return RiskLevel.SAFE, "Account is within safe risk parameters."


# Module-level singleton
live_risk_calculator = LiveRiskCalculator()

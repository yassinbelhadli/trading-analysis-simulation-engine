import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text as sa_text,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base


def _utcnow():
    return datetime.now(timezone.utc)


def _uuid():
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Role
# ---------------------------------------------------------------------------
class Role(Base):
    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    users: Mapped[List["User"]] = relationship(back_populates="role_rel", lazy="selectin")
    permissions: Mapped[List["RolePermission"]] = relationship(back_populates="role", lazy="selectin", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# Permission
# ---------------------------------------------------------------------------
class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    resource: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    __table_args__ = (UniqueConstraint("resource", "action", name="uq_permission_resource_action"),)


# ---------------------------------------------------------------------------
# RolePermission
# ---------------------------------------------------------------------------
class RolePermission(Base):
    __tablename__ = "role_permissions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    role_id: Mapped[str] = mapped_column(String(36), ForeignKey("roles.id"), nullable=False)
    permission_id: Mapped[str] = mapped_column(String(36), ForeignKey("permissions.id"), nullable=False)

    role: Mapped["Role"] = relationship(back_populates="permissions", lazy="selectin")
    permission: Mapped["Permission"] = relationship(lazy="selectin")

    __table_args__ = (UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),)


# ---------------------------------------------------------------------------
# LoginSession
# ---------------------------------------------------------------------------
class LoginSession(Base):
    __tablename__ = "login_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    refresh_token_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    device_info: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped["User"] = relationship(back_populates="sessions", lazy="selectin")


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    telegram_id: Mapped[Optional[int]] = mapped_column(BigInteger, unique=True, nullable=True)
    telegram_username: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    # web auth fields
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("roles.id"), nullable=True)
    account_status: Mapped[str] = mapped_column(String(20), default="active")
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    two_factor_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    two_factor_secret: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    first_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    avatar: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="EN")
    timezone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default="Africa/Casablanca")
    preferences: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")

    # Client's preferred billing currency (USD/EUR/MAD) for multi-currency plans
    billing_currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)

    # relationships
    role_rel: Mapped[Optional["Role"]] = relationship(back_populates="users", lazy="selectin")
    sessions: Mapped[List["LoginSession"]] = relationship(back_populates="user", lazy="selectin", cascade="all, delete-orphan")
    licenses: Mapped[List["License"]] = relationship(back_populates="user", lazy="selectin")
    _subscriptions: Mapped[List["Subscription"]] = relationship(back_populates="user", lazy="selectin")
    _payments: Mapped[List["Payment"]] = relationship(back_populates="user", lazy="selectin", foreign_keys="Payment.user_id")
    accounts: Mapped[List["TradingAccount"]] = relationship(back_populates="user", lazy="selectin")

    @property
    def subscription(self) -> Optional["Subscription"]:
        """Return the most recently created *active* subscription, or ``None``.

        The ``subscriptions`` list may contain historical (expired/cancelled)
        rows — this property ensures code that accesses ``user.subscription``
        always gets the current active one.
        """
        for sub in sorted(self._subscriptions, key=lambda s: s.created_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True):
            if sub.active:
                return sub
        return None
    # No relationship to AuditLog — user_id is an optional string without FK constraint


# ---------------------------------------------------------------------------
# License
# ---------------------------------------------------------------------------
class License(Base):
    __tablename__ = "licenses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    license_key: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    plan: Mapped[str] = mapped_column(String(50), default="standard")
    status: Mapped[str] = mapped_column(String(20), default="active")
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    max_accounts: Mapped[int] = mapped_column(Integer, default=1)
    telegram_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    bound_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    bound_account_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    transfer_locked: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    user: Mapped["User"] = relationship(back_populates="licenses", lazy="selectin")
    accounts: Mapped[List["TradingAccount"]] = relationship(back_populates="license_rel", lazy="selectin")


# ---------------------------------------------------------------------------
# Subscription
# ---------------------------------------------------------------------------
class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    plan: Mapped[str] = mapped_column(String(50), default="free")
    billing_cycle: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    price: Mapped[float] = mapped_column(Float, default=0.0)
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Snapshot fields — preserve what the client purchased even if the plan
    # changes later (plan edits must never rewrite purchase history).
    plan_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    plan_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    plan_duration_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    plan_price_paid: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    plan_currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)  # USD/EUR/MAD
    plan_features: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Coupon tracking
    coupon_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    discount_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)

    # Human-readable subscription number (e.g. SUB-000001)
    subscription_number: Mapped[Optional[str]] = mapped_column(String(20), unique=True, nullable=True)

    # Lifecycle status: PENDING → ACTIVE → CANCELLED | EXPIRED | SUSPENDED | REVOKED
    # PENDING = checkout created, awaiting payment confirmation
    # ACTIVE  = paid and active
    # CANCELLED = user or admin cancelled
    # EXPIRED = past end_date
    # SUSPENDED = temporarily suspended (admin action, payment issue)
    # REVOKED = permanently revoked (fraud, violation)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE", index=True)

    # Suspension/Revocation fields
    suspension_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    suspended_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    suspended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoke_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    user: Mapped["User"] = relationship(back_populates="_subscriptions", lazy="selectin")
    payments: Mapped[List["Payment"]] = relationship(back_populates="subscription", lazy="selectin")


# ---------------------------------------------------------------------------
# TradingAccount
# ---------------------------------------------------------------------------
class TradingAccount(Base):
    __tablename__ = "trading_accounts"

    __table_args__ = (
        Index(
            "uq_active_mt_account_fingerprint",
            "account_fingerprint",
            unique=True,
            postgresql_where=sa_text("removed_at IS NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)

    # account type
    account_type: Mapped[str] = mapped_column(String(20), default="PERSONAL")  # PERSONAL | CHALLENGE | FUNDED | UNKNOWN

    # broker / prop firm
    broker: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    prop_firm: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    program: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    program_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # mt connection
    platform: Mapped[str] = mapped_column(String(10), default="MT5")
    server: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    login: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    encrypted_password: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # user-facing label
    name: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)

    # account details
    account_size: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    demo_real: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    trade_mode: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    leverage: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    balance_snapshot: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    equity_snapshot: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    symbol_mapping: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    account_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    removed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # license binding
    license_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("licenses.id"), nullable=True)
    engine_status: Mapped[str] = mapped_column(String(20), default="WAITING_ACTIVATION")  # WAITING_ACTIVATION | ACTIVE | SUSPENDED | DISABLED

    # status
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    real_trading_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # relationships
    user: Mapped["User"] = relationship(back_populates="accounts", lazy="selectin")
    license_rel: Mapped[Optional["License"]] = relationship(back_populates="accounts", lazy="selectin")
    risk_profile: Mapped[Optional["RiskProfile"]] = relationship(back_populates="account", uselist=False, lazy="selectin")
    scans: Mapped[List["AccountScan"]] = relationship(back_populates="account", lazy="selectin")


# ---------------------------------------------------------------------------
# RiskProfile
# ---------------------------------------------------------------------------
class RiskProfile(Base):
    __tablename__ = "risk_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    account_id: Mapped[str] = mapped_column(String(36), ForeignKey("trading_accounts.id"), unique=True, nullable=False)

    # limits
    daily_loss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_loss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    profit_target: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_risk_trade: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    mode: Mapped[str] = mapped_column(String(20), default="balanced")

    # drawdown baselines
    initial_balance: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    day_start_balance: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    day_start_equity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    daily_high_equity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    drawdown_type: Mapped[str] = mapped_column(String(20), default="static")
    last_risk_update: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # computed values (cached)
    current_daily_loss_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    current_max_loss_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # safety buffer: never risk this percentage of account
    safety_buffer_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=0.5)

    # minimum trading days enforcement (prop firm evaluation)
    min_trading_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    trading_days_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_trade_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    trading_dates: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    account: Mapped["TradingAccount"] = relationship(back_populates="risk_profile", lazy="selectin")


# ---------------------------------------------------------------------------
# AccountScan
# ---------------------------------------------------------------------------
class AccountScan(Base):
    __tablename__ = "account_scans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    account_id: Mapped[str] = mapped_column(String(36), ForeignKey("trading_accounts.id"), nullable=False)

    broker_detected: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    balance_detected: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    equity_detected: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    leverage_detected: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    symbols_detected: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mismatches: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    build: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    timezone_detected: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    scan_status: Mapped[str] = mapped_column(String(20), default="pending")
    scanned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    account: Mapped["TradingAccount"] = relationship(back_populates="scans", lazy="selectin")


# ---------------------------------------------------------------------------
# PaperTrade
# ---------------------------------------------------------------------------
class PaperTrade(Base):
    __tablename__ = "paper_trades"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    account_id: Mapped[str] = mapped_column(String(36), ForeignKey("trading_accounts.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)

    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    stop_loss: Mapped[float] = mapped_column(Float, nullable=False)
    take_profit: Mapped[float] = mapped_column(Float, nullable=False)
    risk_reward: Mapped[float] = mapped_column(Float, default=0.0)
    lot_size: Mapped[float] = mapped_column(Float, default=0.0)
    risk_percent: Mapped[float] = mapped_column(Float, default=0.0)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    rank: Mapped[str] = mapped_column(String(20), default="IGNORE")
    status: Mapped[str] = mapped_column(String(20), default="PLANNED")
    reasons: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    session: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    market_regime: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    candidate_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    close_reason: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    realized_pnl: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    fill_latency_sec: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    trade_duration_sec: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    breakeven_activated: Mapped[bool] = mapped_column(Boolean, default=False)
    breakeven_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    highest_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lowest_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    mfe: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    mae: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    partial_closed: Mapped[bool] = mapped_column(Boolean, default=False)
    partial_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    partial_pnl: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    post_partial_highest_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    post_partial_lowest_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    runner_mfe: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    runner_efficiency: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    realized_r: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    initial_risk_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    validation_batch: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    trade_source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="NORMAL",
        comment="NORMAL | NEWS_DRIVEN — how the trade was initiated",
    )

    account: Mapped["TradingAccount"] = relationship(lazy="selectin")
    user: Mapped["User"] = relationship(lazy="selectin")


# ---------------------------------------------------------------------------
# AuditLog
# ---------------------------------------------------------------------------
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    account_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(10), nullable=False, default="INFO")
    source: Mapped[str] = mapped_column(String(60), nullable=False, default="system")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)

    # No relationship to User — user_id is an optional string without FK constraint


# ---------------------------------------------------------------------------
# PlanDefinition (editable plan configs)
# ---------------------------------------------------------------------------
class PlanDefinition(Base):
    __tablename__ = "plan_definitions"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    price_monthly: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_yearly: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    one_time_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_accounts: Mapped[int] = mapped_column(Integer, default=1)
    max_daily_loss: Mapped[float] = mapped_column(Float, default=500)
    max_risk_per_trade: Mapped[float] = mapped_column(Float, default=0.5)
    features: Mapped[dict] = mapped_column(JSON, default=dict)
    on_sale: Mapped[bool] = mapped_column(Boolean, default=False)
    old_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sale_label: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    # Soft-delete flag: archived plans are hidden from purchase/listing but
    # keep existing subscriptions and promotion FKs intact.
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    # Multi-currency pricing (Decimal for money, NEVER float) — primary prices
    price_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    price_eur: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    price_mad: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)

    # How many days the plan lasts
    duration_days: Mapped[int] = mapped_column(Integer, default=30)

    # Structured feature flags ({"mt5_access": true, "trading_engine": true, ...})
    features_json: Mapped[dict] = mapped_column(JSON, default=dict)

    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Optional badge text (e.g. "Most Popular")
    badge: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    display_order: Mapped[int] = mapped_column(Integer, default=0)


# ---------------------------------------------------------------------------
# Promotion (sale / discount on a specific plan)
# ---------------------------------------------------------------------------
class Promotion(Base):
    __tablename__ = "promotions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    plan_id: Mapped[str] = mapped_column(String(50), ForeignKey("plan_definitions.id"), nullable=False)
    old_price: Mapped[float] = mapped_column(Float, nullable=False)
    new_price: Mapped[float] = mapped_column(Float, nullable=False)
    discount_percent: Mapped[int] = mapped_column(Integer, default=0)
    badge_text: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


# ---------------------------------------------------------------------------
# Coupon (discount code applicable to plan purchases)
# ---------------------------------------------------------------------------
class Coupon(Base):
    __tablename__ = "coupons"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Discount — "percentage" or "fixed_amount"
    discount_type: Mapped[str] = mapped_column(String(20), nullable=False)
    discount_value: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    # Required for fixed_amount, null for percentage
    currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)

    # Validity window
    valid_from: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Limits — max_redemptions null = unlimited
    max_redemptions: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_per_user: Mapped[int] = mapped_column(Integer, default=1)
    min_subscription_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)

    # Eligibility — list of plan IDs, null = all plans
    applicable_plans: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Denormalized stats for performance
    total_redemptions: Mapped[int] = mapped_column(Integer, default=0)
    total_discount_granted: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    redemptions: Mapped[List["CouponRedemption"]] = relationship(back_populates="coupon", lazy="selectin")


# ---------------------------------------------------------------------------
# CouponRedemption (audit trail of each coupon use)
# ---------------------------------------------------------------------------
class CouponRedemption(Base):
    __tablename__ = "coupon_redemptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    coupon_id: Mapped[str] = mapped_column(String(36), ForeignKey("coupons.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    subscription_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("subscriptions.id"), nullable=True)

    original_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    final_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)

    redeemed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # NOTE: intentionally no unique constraint on (coupon_id, user_id) —
    # max_per_user can be greater than 1; per-user limits are enforced in the
    # service layer by counting redemptions.

    coupon: Mapped["Coupon"] = relationship(back_populates="redemptions", lazy="selectin")


# ---------------------------------------------------------------------------
# EABuild (downloadable EA release metadata)
# ---------------------------------------------------------------------------
class EABuild(Base):
    __tablename__ = "ea_builds"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    version: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    release_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    changelog: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    windows_file: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    macos_file: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_latest: Mapped[bool] = mapped_column(Boolean, default=False)
    released_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # approval workflow
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


# ---------------------------------------------------------------------------
# News (admin announcements)
# ---------------------------------------------------------------------------
class News(Base):
    __tablename__ = "news"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="general")
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    telegram_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


# ---------------------------------------------------------------------------
# NewsEvent (economic calendar events from ForexFactory)
# ---------------------------------------------------------------------------
class NewsEvent(Base):
    __tablename__ = "news_events"

    news_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")
    event: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    impact: Mapped[str] = mapped_column(String(10), nullable=False, default="LOW")
    actual: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    forecast: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    previous: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="UPCOMING")
    version: Mapped[int] = mapped_column(Integer, default=1)
    first_seen: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_checked: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    analyzed: Mapped[bool] = mapped_column(Boolean, default=False)
    telegram_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    entry_processed: Mapped[bool] = mapped_column(Boolean, default=False)

    def to_dict(self) -> dict:
        return {
            "news_id": self.news_id,
            "time": self.time.isoformat() if self.time else None,
            "currency": self.currency,
            "event": self.event,
            "impact": self.impact,
            "actual": self.actual,
            "forecast": self.forecast,
            "previous": self.previous,
            "status": self.status,
            "version": self.version,
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_checked": self.last_checked.isoformat() if self.last_checked else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "processed": self.processed,
            "analyzed": self.analyzed,
            "telegram_sent": self.telegram_sent,
            "entry_processed": self.entry_processed,
        }


# ---------------------------------------------------------------------------
# SupportTicket
# ---------------------------------------------------------------------------
class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    ticket_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), default="other")
    status: Mapped[str] = mapped_column(String(20), default="open")
    priority: Mapped[str] = mapped_column(String(10), default="medium")
    escalated: Mapped[bool] = mapped_column(Boolean, default=False)
    escalated_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    escalated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    escalation_target: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # developer | admin | owner
    escalation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assignee_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    assigned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="dashboard")  # dashboard | telegram | admin
    admin_reply: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    replied_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    # NOTE: foreign_keys disambiguates the join — support_tickets has TWO FKs to
    # users (user_id + assignee_id); without it SQLAlchemy raises
    # AmbiguousForeignKeysError on every query touching SupportTicket.user.
    user: Mapped["User"] = relationship(lazy="selectin", foreign_keys="SupportTicket.user_id")
    messages: Mapped[List["TicketMessage"]] = relationship(
        back_populates="ticket", lazy="selectin", cascade="all, delete-orphan", order_by="TicketMessage.created_at"
    )


# ---------------------------------------------------------------------------
# TicketMessage (conversation: client/staff messages + internal staff notes)
# ---------------------------------------------------------------------------
class TicketMessage(Base):
    __tablename__ = "ticket_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    ticket_id: Mapped[str] = mapped_column(String(36), ForeignKey("support_tickets.id"), nullable=False, index=True)
    author_user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    author_role: Mapped[str] = mapped_column(String(20), default="client")  # client | support | developer | admin | owner | system
    author_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    kind: Mapped[str] = mapped_column(String(10), default="message")  # message | note (internal)
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)

    ticket: Mapped["SupportTicket"] = relationship(back_populates="messages", lazy="selectin")


# ---------------------------------------------------------------------------
# VerificationToken (email verification / password reset)
# ---------------------------------------------------------------------------
class VerificationToken(Base):
    __tablename__ = "verification_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # verify_email | reset_password
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


# ---------------------------------------------------------------------------
# SiteSetting (key-value configuration editable from the dashboard)
# ---------------------------------------------------------------------------
class SiteSetting(Base):
    __tablename__ = "site_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="general", index=True)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
    updated_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)


# ---------------------------------------------------------------------------
# CalendarEvent (economic calendar — single source of truth)
# ---------------------------------------------------------------------------
# Imported from a dedicated module to keep models.py manageable.
# The CalendarEvent model shares the same Base, so create_all picks it up.
import database.calendar_models  # noqa: E402, F401


# ---------------------------------------------------------------------------
# Payment (tracks every payment attempt for subscription purchases)
# ---------------------------------------------------------------------------
class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    payment_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)

    # Relationships
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    subscription_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("subscriptions.id"), nullable=True, index=True)
    plan_id: Mapped[str] = mapped_column(String(50), ForeignKey("plan_definitions.id"), nullable=False)
    coupon_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("coupons.id"), nullable=True)

    # Amounts (NEVER float — Numeric only)
    original_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    final_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)

    # Provider tracking
    payment_provider: Mapped[str] = mapped_column(String(30), nullable=False, default="none")  # stripe | paypal | none
    provider_payment_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    provider_checkout_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    payment_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # card | bank_transfer | etc

    # Status lifecycle: PENDING → PROCESSING → PAID | FAILED | CANCELLED | REFUNDED
    # Manual payments also use: PENDING → PENDING_VERIFICATION → PAID | FAILED
    # Crypto payments use: CREATED → AWAITING_PAYMENT → TRANSACTION_DETECTED → CONFIRMING → PAID
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING", index=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Payment method classification: automatic | manual | manual_crypto
    payment_method_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Manual payment fields (used when payment_method_type = "manual" or "manual_crypto")
    manual_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    manual_proof_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    manual_instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Payer identity captured at proof submission (owner verification data)
    payer_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    payer_phone: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    payment_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    amount_paid: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    approved_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    internal_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # --- Crypto payment fields (used when payment_method_type = "manual_crypto") ---
    deposit_address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    deposit_network: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    coin_ticker: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    transaction_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    sender_address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    confirmation_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
    expected_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8), nullable=True)
    detected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expired_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verification_type: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)  # automatic | manual_review | owner_override
    verified_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    proof_screenshot_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    proof_submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    proof_tx_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    proof_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8), nullable=True)
    proof_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Snapshot of plan details at purchase time (immutable)
    plan_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    plan_duration_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Coupon snapshot
    coupon_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Provider event tracking for idempotency
    provider_event_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    # Metadata (provider-specific data, webhook payloads, etc)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    refunded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship(lazy="selectin", foreign_keys="Payment.user_id")
    subscription: Mapped[Optional["Subscription"]] = relationship(lazy="selectin", foreign_keys="Payment.subscription_id")
    plan: Mapped["PlanDefinition"] = relationship(lazy="selectin", foreign_keys="Payment.plan_id")
    coupon: Mapped[Optional["Coupon"]] = relationship(lazy="selectin", foreign_keys="Payment.coupon_id")

    # Valid status transitions (state machine)
    # PENDING → PAID is allowed because some providers send a single
    # "completed" event without a separate processing step.
    # PENDING_VERIFICATION is for manual payments awaiting owner/billing approval.
    # Crypto-specific states: AWAITING_PAYMENT → TRANSACTION_DETECTED → CONFIRMING → PAID
    # EXPIRED: manual payments that were never submitted before their deadline (REQ 7/9)
    # REJECTED: manual payments whose proof was refused by the owner (distinct from FAILED)
    VALID_TRANSITIONS: dict = {
        "PENDING": ["PROCESSING", "PAID", "CANCELLED", "FAILED", "PENDING_VERIFICATION", "EXPIRED"],
        "PROCESSING": ["PAID", "FAILED", "CANCELLED"],
        "PENDING_VERIFICATION": ["PAID", "FAILED", "CANCELLED", "REJECTED"],
        "AWAITING_PAYMENT": ["TRANSACTION_DETECTED", "EXPIRED", "CANCELLED"],
        "TRANSACTION_DETECTED": ["CONFIRMING", "AMOUNT_MISMATCH", "WRONG_NETWORK", "MANUAL_REVIEW"],
        "CONFIRMING": ["PAID", "FAILED", "MANUAL_REVIEW"],
        "MANUAL_REVIEW": ["PAID", "FAILED"],
        "EXPIRED": [],      # terminal
        "REJECTED": [],     # terminal (owner refused the proof)
        "AMOUNT_MISMATCH": ["MANUAL_REVIEW"],  # can be manually reviewed
        "WRONG_NETWORK": [],  # terminal
        "PAID": ["REFUNDED", "SUSPENDED"],
        "SUSPENDED": ["PAID", "REFUNDED"],  # can be reactivated or refunded
        "FAILED": [],      # terminal
        "CANCELLED": [],    # terminal
        "REFUNDED": [],     # terminal
    }

    def can_transition_to(self, new_status: str) -> bool:
        """Check if this payment can transition to the given status."""
        return new_status in self.VALID_TRANSITIONS.get(self.status, [])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "payment_number": self.payment_number,
            "user_id": self.user_id,
            "subscription_id": self.subscription_id,
            "plan_id": self.plan_id,
            "plan_name": self.plan_name,
            "plan_duration_days": self.plan_duration_days,
            "original_amount": float(self.original_amount) if self.original_amount else 0,
            "discount_amount": float(self.discount_amount) if self.discount_amount else 0,
            "final_amount": float(self.final_amount) if self.final_amount else 0,
            "currency": self.currency,
            "coupon_code": self.coupon_code,
            "payment_provider": self.payment_provider,
            "payment_method_type": self.payment_method_type,
            "provider_payment_id": self.provider_payment_id,
            "payment_method": self.payment_method,
            "status": self.status,
            "failure_reason": self.failure_reason,
            # Manual payment fields
            "manual_reference": self.manual_reference,
            "manual_proof_url": self.manual_proof_url,
            "manual_instructions": self.manual_instructions,
            "payer_name": self.payer_name,
            "payer_phone": self.payer_phone,
            "payment_date": self.payment_date.isoformat() if self.payment_date else None,
            "amount_paid": float(self.amount_paid) if self.amount_paid is not None else None,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "rejected_at": self.rejected_at.isoformat() if self.rejected_at else None,
            "rejection_reason": self.rejection_reason,
            "internal_notes": self.internal_notes,
            # Crypto payment fields
            "deposit_address": self.deposit_address,
            "deposit_network": self.deposit_network,
            "coin_ticker": self.coin_ticker,
            "transaction_hash": self.transaction_hash,
            "sender_address": self.sender_address,
            "confirmation_count": self.confirmation_count,
            "expected_amount": float(self.expected_amount) if self.expected_amount else None,
            "detected_at": self.detected_at.isoformat() if self.detected_at else None,
            "confirmed_at": self.confirmed_at.isoformat() if self.confirmed_at else None,
            "expired_at": self.expired_at.isoformat() if self.expired_at else None,
            "verification_type": self.verification_type,
            "verified_by": self.verified_by,
            "proof_screenshot_url": self.proof_screenshot_url,
            "proof_submitted_at": self.proof_submitted_at.isoformat() if self.proof_submitted_at else None,
            "proof_tx_hash": self.proof_tx_hash,
            "proof_amount": float(self.proof_amount) if self.proof_amount else None,
            "proof_note": self.proof_note,
            # Timestamps
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "paid_at": self.paid_at.isoformat() if self.paid_at else None,
            "failed_at": self.failed_at.isoformat() if self.failed_at else None,
            "cancelled_at": self.cancelled_at.isoformat() if self.cancelled_at else None,
            "refunded_at": self.refunded_at.isoformat() if self.refunded_at else None,
        }


# ---------------------------------------------------------------------------
# Receipt (generated after successful payment — immutable record)
# ---------------------------------------------------------------------------
class Receipt(Base):
    __tablename__ = "receipts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    receipt_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)

    # Relationships
    payment_id: Mapped[str] = mapped_column(String(36), ForeignKey("payments.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    subscription_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("subscriptions.id"), nullable=True)

    # Snapshot of what was purchased (immutable at time of payment)
    plan_name: Mapped[str] = mapped_column(String(100), nullable=False)
    plan_duration_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    original_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    final_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    coupon_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    payment_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    payment_status: Mapped[str] = mapped_column(String(20), nullable=False, default="PAID")

    # Crypto receipt fields
    coin_ticker: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    deposit_network: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    transaction_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    expected_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8), nullable=True)
    paid_amount_crypto: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8), nullable=True)

    # Timestamps
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    subscription_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    subscription_expiration: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # Relationships
    payment: Mapped["Payment"] = relationship(lazy="selectin", foreign_keys="Receipt.payment_id")
    user: Mapped["User"] = relationship(lazy="selectin", foreign_keys="Receipt.user_id")
    subscription: Mapped[Optional["Subscription"]] = relationship(lazy="selectin", foreign_keys="Receipt.subscription_id")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "receipt_number": self.receipt_number,
            "payment_id": self.payment_id,
            "plan_name": self.plan_name,
            "plan_duration_days": self.plan_duration_days,
            "original_amount": float(self.original_amount) if self.original_amount else 0,
            "discount_amount": float(self.discount_amount) if self.discount_amount else 0,
            "final_amount": float(self.final_amount) if self.final_amount else 0,
            "currency": self.currency,
            "coupon_code": self.coupon_code,
            "payment_method": self.payment_method,
            "payment_status": self.payment_status,
            # Crypto receipt fields
            "coin_ticker": self.coin_ticker,
            "deposit_network": self.deposit_network,
            "transaction_hash": self.transaction_hash,
            "expected_amount": float(self.expected_amount) if self.expected_amount else None,
            "paid_amount_crypto": float(self.paid_amount_crypto) if self.paid_amount_crypto else None,
            # Timestamps
            "paid_at": self.paid_at.isoformat() if self.paid_at else None,
            "subscription_start": self.subscription_start.isoformat() if self.subscription_start else None,
            "subscription_expiration": self.subscription_expiration.isoformat() if self.subscription_expiration else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# PaymentMethodConfig (owner-configurable payment instructions for clients)
# ---------------------------------------------------------------------------
class PaymentMethodConfig(Base):
    __tablename__ = "payment_method_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    method_id: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    method_type: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    beneficiary_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    account_rib: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    phone_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    branch: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reference_instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Whether the client must enter a payment reference before submitting proof (REQ 6)
    reference_required: Mapped[bool] = mapped_column(Boolean, default=True)
    # Client-facing fields the owner requires for this method (e.g. ["reference", "payer_name", "payer_phone"])
    required_fields: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    optional_fields: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Crypto-specific (manual_crypto): static wallet address + network the client pays to
    wallet_address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    network: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # How long a created manual payment stays valid before it expires (REQ 7)
    expires_hours: Mapped[int] = mapped_column(Integer, default=72)
    # --- Configuration-driven payment method fields (REQ: owner-defined) ---
    # Short marketing/description text shown to the client (separate from information).
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Structured information blocks: [{"label": "Beneficiary", "value": "..."}, ...]
    information: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    # Client input field definitions: [{"key","label","type","required","placeholder","validation"}, ...]
    # type ∈ text|number|phone|date|datetime|email|image|file
    client_fields: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    # Whether a receipt/photo upload is required for this method (mandatory for manual).
    receipt_required: Mapped[bool] = mapped_column(Boolean, default=True)
    # Automatic-method fields: supported currencies, provider name, gateway status.
    currencies: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    provider_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    gateway_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "method_id": self.method_id,
            "method_type": self.method_type,
            "display_name": self.display_name,
            "beneficiary_name": self.beneficiary_name,
            "account_rib": self.account_rib,
            "phone_number": self.phone_number,
            "branch": self.branch,
            "instructions": self.instructions,
            "reference_instructions": self.reference_instructions,
            "reference_required": self.reference_required,
            "required_fields": self.required_fields,
            "optional_fields": self.optional_fields,
            "wallet_address": self.wallet_address,
            "network": self.network,
            "expires_hours": self.expires_hours,
            "description": self.description,
            "information": self.information,
            "client_fields": self.client_fields,
            "receipt_required": self.receipt_required,
            "currencies": self.currencies,
            "provider_name": self.provider_name,
            "gateway_status": self.gateway_status,
            "is_active": self.is_active,
            "display_order": self.display_order,
            "archived": self.archived,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

"""
Safe, migration-free ALTER TABLE helpers.

Existing databases that predate a column are updated by checking
``information_schema`` before adding the column. Fresh databases create
all columns via ``Base.metadata.create_all`` and are unaffected.
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# (table, column, column_definition)
COLUMNS_TO_ENSURE = [
    ("risk_profiles", "min_trading_days", "INTEGER"),
    ("risk_profiles", "trading_days_count", "INTEGER NOT NULL DEFAULT 0"),
    ("risk_profiles", "first_trade_date", "TIMESTAMPTZ"),
    ("risk_profiles", "trading_dates", "TEXT"),
    # Configuration-driven payment methods (owner-defined description,
    # information blocks, client input fields, receipt requirement).
    ("payment_method_configs", "description", "TEXT"),
    ("payment_method_configs", "information", "JSONB"),
    ("payment_method_configs", "client_fields", "JSONB"),
    ("payment_method_configs", "receipt_required", "BOOLEAN DEFAULT TRUE"),
    ("payment_method_configs", "currencies", "JSONB"),
    ("payment_method_configs", "provider_name", "VARCHAR(100)"),
    ("payment_method_configs", "gateway_status", "VARCHAR(50)"),
]


async def ensure_schema_columns(session: AsyncSession) -> None:
    """Add missing columns to existing tables (idempotent ALTER TABLE)."""
    for table, column, col_type in COLUMNS_TO_ENSURE:
        check = await session.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = :table AND column_name = :column"
            ),
            {"table": table, "column": column},
        )
        if check.scalar() is None:
            await session.execute(
                text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
            )
    await session.flush()

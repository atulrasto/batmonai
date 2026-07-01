"""Add per-battery voltage thresholds and per-sensor config for rules engine

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Per-battery configurable thresholds (defaults suit 12 V flooded lead-acid)
    op.add_column("batteries", sa.Column(
        "low_v_threshold",
        sa.Numeric(6, 3),
        nullable=False,
        server_default="11.5",
    ))
    op.add_column("batteries", sa.Column(
        "high_v_threshold",
        sa.Numeric(6, 3),
        nullable=False,
        server_default="14.5",
    ))
    # rs485_sensors.config was already created in 0001 (nullable JSONB).
    # Set NOT NULL + default server-side so existing NULLs get a default.
    op.execute("UPDATE rs485_sensors SET config = '{}' WHERE config IS NULL")
    op.alter_column("rs485_sensors", "config",
                    existing_type=JSONB(),
                    nullable=False,
                    server_default="{}")


def downgrade() -> None:
    op.drop_column("batteries", "low_v_threshold")
    op.drop_column("batteries", "high_v_threshold")
    # Revert config column back to nullable (don't drop — it came from 0001)
    op.alter_column("rs485_sensors", "config",
                    existing_type=JSONB(),
                    nullable=True,
                    server_default=None)

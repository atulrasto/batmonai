"""Add webhook_url to clients

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("clients", sa.Column(
        "webhook_url",
        sa.String(),
        nullable=True,
        server_default=None,
    ))


def downgrade() -> None:
    op.drop_column("clients", "webhook_url")

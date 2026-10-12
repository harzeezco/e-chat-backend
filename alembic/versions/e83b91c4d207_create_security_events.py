"""create normalized security events

Revision ID: e83b91c4d207
Revises: d2c7e4b15a09
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e83b91c4d207"
down_revision: Union[str, Sequence[str], None] = "d2c7e4b15a09"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "security_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("login_id", sa.String(length=36), nullable=True),
        sa.Column("device_id", sa.String(), sa.ForeignKey("user_devices.id"), nullable=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("resource_type", sa.String(), nullable=True),
        sa.Column("resource_id", sa.String(), nullable=True),
        sa.Column("ip_address", sa.String(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("event_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    for column in ("user_id", "login_id", "device_id", "event_type", "created_at"):
        op.create_index(f"ix_security_events_{column}", "security_events", [column])


def downgrade() -> None:
    for column in ("created_at", "event_type", "device_id", "login_id", "user_id"):
        op.drop_index(f"ix_security_events_{column}", table_name="security_events")
    op.drop_table("security_events")
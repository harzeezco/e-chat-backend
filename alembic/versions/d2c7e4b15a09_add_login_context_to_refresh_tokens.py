"""add login context to refresh tokens

Revision ID: d2c7e4b15a09
Revises: ac3928d6e84b
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d2c7e4b15a09"
down_revision: Union[str, Sequence[str], None] = "ac3928d6e84b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("refresh_tokens", sa.Column("login_id", sa.String(length=36), nullable=True))
    op.add_column("refresh_tokens", sa.Column("device_id", sa.String(), nullable=True))
    op.add_column("refresh_tokens", sa.Column("new_device_at_login", sa.Boolean(), nullable=True))
    op.create_index("ix_refresh_tokens_login_id", "refresh_tokens", ["login_id"])
    op.create_index("ix_refresh_tokens_device_id", "refresh_tokens", ["device_id"])
    op.create_foreign_key(
        "fk_refresh_tokens_device_id_user_devices",
        "refresh_tokens",
        "user_devices",
        ["device_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_refresh_tokens_device_id_user_devices", "refresh_tokens", type_="foreignkey")
    op.drop_index("ix_refresh_tokens_device_id", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_login_id", table_name="refresh_tokens")
    op.drop_column("refresh_tokens", "new_device_at_login")
    op.drop_column("refresh_tokens", "device_id")
    op.drop_column("refresh_tokens", "login_id")

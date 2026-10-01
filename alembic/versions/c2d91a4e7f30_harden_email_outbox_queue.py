"""harden email outbox queue

Revision ID: c2d91a4e7f30
Revises: 760b11a8b9c0
Create Date: 2026-09-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c2d91a4e7f30"
down_revision: Union[str, Sequence[str], None] = "760b11a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("email_outbox", sa.Column("processing_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("email_outbox", sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        "UPDATE email_outbox SET processing_at = now() WHERE status = 'processing' AND processing_at IS NULL"
    )
    op.create_index(
        "ix_email_outbox_pending_schedule",
        "email_outbox",
        ["status", "next_attempt_at", "created_at"],
    )
    op.create_index(
        "ix_email_outbox_processing_lease",
        "email_outbox",
        ["status", "processing_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_email_outbox_processing_lease", table_name="email_outbox")
    op.drop_index("ix_email_outbox_pending_schedule", table_name="email_outbox")
    op.drop_column("email_outbox", "next_attempt_at")
    op.drop_column("email_outbox", "processing_at")

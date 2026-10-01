from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, func, JSON, DateTime
from datetime import datetime
from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True)

    user_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    action: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    resource_type: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    resource_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    ip_address: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    user_agent: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    event_data: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

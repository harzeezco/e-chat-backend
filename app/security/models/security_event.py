from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SecurityEvent(Base):
    __tablename__ = "security_events"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
    )

    # Who performed the action
    user_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    # Which authenticated login/session produced the event
    session_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("sessions.id"),
        nullable=True,
        index=True,
    )

    # Which known/observed device context was involved
    device_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("user_devices.id"),
        nullable=True,
        index=True,
    )

    # What security-relevant thing happened
    event_type: Mapped[str] = mapped_column(
        String,
        nullable=False,
        index=True,
    )

    # Optional resource affected
    resource_type: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    resource_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    # Network/context information
    ip_address: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    user_agent: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Extra structured evidence about the event
    event_data: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    # When the event occurred
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

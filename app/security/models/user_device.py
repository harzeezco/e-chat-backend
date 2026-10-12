from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserDevice(Base):
    __tablename__ = "user_devices"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "identifier_hash",
            name="uq_user_devices_user_identifier",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    identifier_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

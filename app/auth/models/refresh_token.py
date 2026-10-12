from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    jti: Mapped[str] = mapped_column(String, primary_key=True)

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"),
                                         nullable=False, index=True)

    # Shared by every token issued from one successful login. Nullable while
    # refresh tokens issued before this migration are still valid.
    login_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    device_id: Mapped[str | None] = mapped_column(
        ForeignKey("user_devices.id"), nullable=True, index=True
    )

    # None means the device was not recorded when this login took place.
    new_device_at_login: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )

    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True),
                                                        nullable=True,)

    replaced_by_jti: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

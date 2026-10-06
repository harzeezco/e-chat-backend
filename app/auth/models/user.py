from app.database import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Enum as SqlEnum, DateTime, func
from enum import Enum
from datetime import datetime


class UserRole(str, Enum):
    CUSTOMER = "customer"
    ADMIN = "admin"


class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING = "pending"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    
    password_hash: Mapped[str] = mapped_column(
        String, nullable=False)
    
    role: Mapped[UserRole] = mapped_column(
        SqlEnum(
            UserRole,
            name="userrole",
            values_callable=lambda enum_cls: [
                member.value for member in enum_cls],
        ),
        nullable=False,
    )
    
    status: Mapped[UserStatus] = mapped_column(
        SqlEnum(
            UserStatus,
            name="userstatus",
            values_callable=lambda enum_cls: [
                member.value for member in enum_cls
            ],
        ),
        nullable=False,
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),

    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

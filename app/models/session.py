from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey, Enum as SqlEnum
from .transaction import Transaction
from app.database import Base
from enum import Enum


class CustomerType(str, Enum):
    INDIVIDUAL = "Individual"
    BUSINESS = "Business"


class Session(Base):
    __tablename__ = "session"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String)
    customer_type: Mapped[CustomerType] = mapped_column(
        SqlEnum(CustomerType), nullable=False)

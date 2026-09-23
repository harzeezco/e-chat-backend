from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey
from app.database import Base
from .customer import Customer


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"))

    amount: Mapped[int] = mapped_column()
    currency: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)

    customer: Mapped[list["Customer"]] = relationship(
        back_populates='transactions')

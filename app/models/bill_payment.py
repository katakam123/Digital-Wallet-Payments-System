
from sqlalchemy import (
    Column,
    Integer,
    String,
    Numeric,
    ForeignKey,
    Index,
)

from app.database import Base
from app.models.base import TimestampMixin


class BillPayment(Base, TimestampMixin):
    __tablename__ = "bill_payments"

    __table_args__ = (
        Index("ix_bill_payment_user", "user_id"),
        Index("ix_bill_payment_reference", "provider_reference"),
    )

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
    )

    transaction_id = Column(
        Integer,
        ForeignKey("financial_transactions.id"),
        nullable=False,
        unique=True,
    )

    bill_type = Column(
        String(30),
        nullable=False,
    )

    provider = Column(
        String(100),
        nullable=False,
    )

    customer_identifier = Column(
        String(50),
        nullable=False,
    )

    amount = Column(
        Numeric(12, 2),
        nullable=False,
    )

    provider_reference = Column(
        String(100),
        nullable=False,
        unique=True,
    )

    status = Column(
        String(20),
        nullable=False,
        default="Success",
    )

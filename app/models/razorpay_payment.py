
from sqlalchemy import (
    Column,
    Integer,
    String,
    Numeric,
    ForeignKey,
    UniqueConstraint,
    Index,
)

from app.database import Base
from app.models.base import TimestampMixin


class RazorpayPayment(Base, TimestampMixin):
    __tablename__ = "razorpay_payments"

    __table_args__ = (
        UniqueConstraint(
            "razorpay_order_id",
            name="uq_razorpay_order_id",
        ),
        UniqueConstraint(
            "razorpay_payment_id",
            name="uq_razorpay_payment_id",
        ),
        Index("ix_razorpay_user_status", "user_id", "status"),
    )

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
    )

    amount = Column(Numeric(12, 2), nullable=False)

    currency = Column(
        String(3),
        nullable=False,
        default="INR",
    )

    razorpay_order_id = Column(
        String(100),
        nullable=False,
    )

    razorpay_payment_id = Column(
        String(100),
        nullable=True,
    )

    status = Column(
        String(20),
        nullable=False,
        default="Created",
    )

    transaction_id = Column(
        Integer,
        ForeignKey("financial_transactions.id"),
        nullable=True,
        unique=True,
    )

    failure_reason = Column(
        String(500),
        nullable=True,
    )

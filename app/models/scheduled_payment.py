
from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    Numeric,
    DateTime,
    Boolean,
    CheckConstraint,
    Index,
)

from app.database import Base
from app.models.base import TimestampMixin


class ScheduledPayment(Base, TimestampMixin):
    __tablename__ = "scheduled_payments"

    __table_args__ = (
        CheckConstraint(
            "amount >= 1",
            name="ck_scheduled_payment_amount"
        ),
        CheckConstraint(
            "frequency IN ('Daily', 'Weekly', 'Monthly')",
            name="ck_scheduled_payment_frequency"
        ),
        CheckConstraint(
            "status IN ('Active', 'Paused', 'Completed', 'Cancelled')",
            name="ck_scheduled_payment_status"
        ),
        Index("ix_scheduled_payment_due", "status", "next_run_at"),
        Index("ix_scheduled_payment_sender", "sender_user_id"),
    )

    id = Column(Integer, primary_key=True, index=True)

    sender_user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
    )

    recipient_user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
    )

    amount = Column(Numeric(12, 2), nullable=False)

    frequency = Column(String(20), nullable=False)

    # Used for monthly payments: 1 through 28.
    day_of_month = Column(Integer, nullable=True)

    next_run_at = Column(DateTime, nullable=False)

    end_at = Column(DateTime, nullable=True)

    status = Column(
        String(20),
        nullable=False,
        default="Active",
    )

    description = Column(String(255), nullable=True)

    execution_count = Column(Integer, nullable=False, default=0)

    last_run_at = Column(DateTime, nullable=True)

    is_processing = Column(Boolean, nullable=False, default=False)

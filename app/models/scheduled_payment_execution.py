
from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    Numeric,
    DateTime,
    UniqueConstraint,
    Index,
)

from app.database import Base
from app.models.base import TimestampMixin


class ScheduledPaymentExecution(Base, TimestampMixin):
    __tablename__ = "scheduled_payment_executions"

    __table_args__ = (
        UniqueConstraint(
            "scheduled_payment_id",
            "scheduled_for",
            name="uq_scheduled_payment_occurrence",
        ),
        Index("ix_scheduled_execution_status", "status"),
    )

    id = Column(Integer, primary_key=True, index=True)

    scheduled_payment_id = Column(
        Integer,
        ForeignKey("scheduled_payments.id"),
        nullable=False,
    )

    scheduled_for = Column(DateTime, nullable=False)

    amount = Column(Numeric(12, 2), nullable=False)

    status = Column(
        String(20),
        nullable=False,
        default="Pending",
    )

    transaction_ref = Column(String(100), nullable=True)

    failure_reason = Column(String(500), nullable=True)

    processed_at = Column(DateTime, nullable=True)

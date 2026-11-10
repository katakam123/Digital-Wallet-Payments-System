
from sqlalchemy import (
    Column,
    Integer,
    String,
    Numeric,
    DateTime,
    ForeignKey,
    CheckConstraint,
    Index,
)
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.base import TimestampMixin


class Withdrawal(Base, TimestampMixin):
    __tablename__ = "withdrawals"

    __table_args__ = (
        CheckConstraint(
            "amount >= 100",
            name="ck_withdrawal_minimum_amount",
        ),
        CheckConstraint(
            "status IN ('Pending', 'Completed', 'Failed')",
            name="ck_withdrawal_status",
        ),
        Index(
            "ix_withdrawals_status_created_at",
            "status",
            "created_at",
        ),
        Index(
            "ix_withdrawals_user_id",
            "user_id",
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    transaction_id = Column(
        Integer,
        ForeignKey("financial_transactions.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )

    bank_account_id = Column(
        Integer,
        ForeignKey("bank_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )

    amount = Column(
        Numeric(12, 2),
        nullable=False,
    )

    status = Column(
        String(20),
        nullable=False,
        default="Pending",
    )

    processed_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    failure_reason = Column(
        String(255),
        nullable=True,
    )

    user = relationship("User")

    bank_account = relationship("BankAccount")

    transaction = relationship("FinancialTransaction")

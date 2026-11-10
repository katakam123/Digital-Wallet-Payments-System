
from decimal import Decimal

from sqlalchemy import (
    Integer,
    String,
    Numeric,
    ForeignKey,
    DateTime,
    CheckConstraint,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin


class Cashback(Base, TimestampMixin):

    __tablename__ = "cashbacks"

    __table_args__ = (
        UniqueConstraint(
            "payment_transaction_id",
            name="uq_cashback_payment_transaction",
        ),
        CheckConstraint(
            "amount > 0",
            name="ck_cashback_amount_positive",
        ),
        CheckConstraint(
            "status IN ('Pending', 'Credited', 'Cancelled')",
            name="ck_cashback_status",
        ),
        Index(
            "ix_cashback_status_available_at",
            "status",
            "available_at",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    payment_transaction_id: Mapped[int] = mapped_column(
        ForeignKey("financial_transactions.id"),
        nullable=False,
    )

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    merchant_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="Pending",
        nullable=False,
        index=True,
    )

    available_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    credited_transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("financial_transactions.id"),
        nullable=True,
    )

    payment_transaction = relationship(
        "FinancialTransaction",
        foreign_keys=[payment_transaction_id],
    )

    credited_transaction = relationship(
        "FinancialTransaction",
        foreign_keys=[credited_transaction_id],
    )

    customer = relationship(
        "User",
        foreign_keys=[customer_id],
    )

    merchant = relationship(
        "User",
        foreign_keys=[merchant_id],
    )

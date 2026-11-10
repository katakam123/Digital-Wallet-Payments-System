from decimal import Decimal

from sqlalchemy import (
    Integer,
    String,
    Numeric,
    ForeignKey,
    Boolean,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin


class FinancialTransaction(Base, TimestampMixin):
    __tablename__ = "financial_transactions"

    __table_args__ = (
        UniqueConstraint(
            "transaction_ref",
            name="uq_financial_transaction_ref",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    transaction_ref: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        unique=True,
        index=True,
    )

    type: Mapped[str] = mapped_column(
        String(40),
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

    initiated_by: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    is_flagged: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Used to connect a reversal to the original transaction.
    reversal_of_id: Mapped[int | None] = mapped_column(
        ForeignKey("financial_transactions.id"),
        nullable=True,
    )

    entries = relationship(
        "LedgerEntry",
        back_populates="transaction",
        order_by="LedgerEntry.id",
    )

    related_transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("financial_transactions.id"),
        nullable=True,
        index=True,
    )

    related_transaction = relationship(
        "FinancialTransaction",
        remote_side="FinancialTransaction.id",
        foreign_keys=[related_transaction_id],
    )


    initiator = relationship("User")
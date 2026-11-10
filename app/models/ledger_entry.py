from decimal import Decimal

from sqlalchemy import (
    Integer,
    String,
    Numeric,
    ForeignKey,
    CheckConstraint,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin


class LedgerEntry(Base, TimestampMixin):
    __tablename__ = "ledger_entries"

    __table_args__ = (
        CheckConstraint(
            "amount > 0",
            name="ck_ledger_entry_amount_positive",
        ),
        CheckConstraint(
            "entry_type IN ('Debit', 'Credit')",
            name="ck_ledger_entry_type",
        ),
        UniqueConstraint(
            "transaction_id",
            "account_id",
            "entry_type",
            name="uq_ledger_transaction_account_type",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("financial_transactions.id"),
        nullable=False,
        index=True,
    )

    account_id: Mapped[int] = mapped_column(
        ForeignKey("ledger_accounts.id"),
        nullable=False,
        index=True,
    )

    entry_type: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    balance_after: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    transaction = relationship(
        "FinancialTransaction",
        back_populates="entries",
    )

    account = relationship(
        "LedgerAccount",
        back_populates="entries",
    )
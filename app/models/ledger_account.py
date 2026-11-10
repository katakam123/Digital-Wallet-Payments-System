
from decimal import Decimal

from sqlalchemy import (
    Integer,
    String,
    ForeignKey,
    Numeric,
    UniqueConstraint,
    CheckConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin


class LedgerAccount(Base, TimestampMixin):

    __tablename__ = "ledger_accounts"

    __table_args__ = (
        UniqueConstraint(
            "wallet_id",
            name="uq_ledger_account_wallet",
        ),
        UniqueConstraint(
            "system_code",
            name="uq_ledger_account_system_code",
        ),
        CheckConstraint(
            "normal_balance IN ('Debit', 'Credit')",
            name="ck_ledger_account_normal_balance",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    account_type: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        index=True,
    )

    wallet_id: Mapped[int | None] = mapped_column(
        ForeignKey("wallets.id"),
        nullable=True,
    )

    system_code: Mapped[str | None] = mapped_column(
        String(60),
        nullable=True,
    )

    current_balance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=Decimal("0.00"),
        nullable=False,
    )

    normal_balance: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="Credit",
        server_default="Credit",
    )

    wallet = relationship(
        "Wallet",
        back_populates="ledger_account",
    )

    entries = relationship(
        "LedgerEntry",
        back_populates="account",
    )

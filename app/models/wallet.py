
import secrets
from decimal import Decimal

from sqlalchemy import (
    Integer,
    ForeignKey,
    Numeric,
    String,
    CheckConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.base import TimestampMixin


def generate_wallet_number():
    number = secrets.randbelow(900000000) + 100000000
    return f"WAL-{number}"


class Wallet(Base, TimestampMixin):

    __tablename__ = "wallets"

    __table_args__ = (
        CheckConstraint(
            "balance >= 0",
            name="ck_wallet_balance_nonnegative"
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        unique=True,
        nullable=False,
        index=True
    )

    wallet_number: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        nullable=False,
        default=generate_wallet_number
    )

    balance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=Decimal("0.00"),
        nullable=False
    )

    kyc_level: Mapped[str] = mapped_column(
        String(20),
        default="Minimum",
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="Active",
        nullable=False
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        default="INR",
        nullable=False
    )

    freeze_reason: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True
    )

    user = relationship(
        "User",
        back_populates="wallet"
    )
    ledger_account = relationship(
        "LedgerAccount",
        back_populates="wallet",
        uselist=False,
    )

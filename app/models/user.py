
from datetime import datetime

from sqlalchemy import (
    String,
    Boolean,
    Integer,
    DateTime,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.database import Base
from app.models.base import TimestampMixin


class User(Base, TimestampMixin):

    __tablename__ = "users"

    # ==============================================
    # PRIMARY KEY
    # ==============================================

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    # ==============================================
    # BASIC USER INFORMATION
    # ==============================================

    full_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )

    phone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # ==============================================
    # USER ROLE
    # ==============================================

    role: Mapped[str] = mapped_column(
        String(20),
        default="User",
        nullable=False,
    )

    # ==============================================
    # MERCHANT INFORMATION
    # ==============================================

    business_name: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    business_category: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    merchant_code: Mapped[str | None] = mapped_column(
        String(20),
        unique=True,
        index=True,
        nullable=True,
    )

    # ==============================================
    # ACCOUNT STATUS
    # ==============================================

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # ==============================================
    # KYC STATUS
    # ==============================================

    kyc_status: Mapped[str] = mapped_column(
        String(20),
        default="Pending",
        nullable=False,
    )

    # ==============================================
    # WALLET RELATIONSHIP
    # ==============================================

    wallet = relationship(
        "Wallet",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # ==============================================
    # BANK ACCOUNT RELATIONSHIP
    # ==============================================

    bank_accounts = relationship(
        "BankAccount",
        back_populates="user",
        cascade="save-update, merge",
    )

    # ==============================================
    # KYC RELATIONSHIP
    # ==============================================

    kyc_records = relationship(
        "KYC",
        back_populates="user",
    )

    # ==============================================
    # TRANSACTION PIN
    # ==============================================

    transaction_pin_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    pin_failed_attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    pin_locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    pin_reset_verified_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # ==============================================
    # OTP AUTHORIZATION
    # ==============================================

    high_value_transfer_verified_until: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    add_bank_verified_until: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

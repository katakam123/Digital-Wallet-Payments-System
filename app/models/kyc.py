
from datetime import date

from sqlalchemy import (
    Integer,
    String,
    Date,
    ForeignKey,
    Index
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin


class KYC(Base, TimestampMixin):

    __tablename__ = "kyc_records"

    __table_args__ = (
        Index("ix_kyc_user_status", "user_id", "status"),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    pan_number: Mapped[str] = mapped_column(
        String(10),
        nullable=False
    )

    aadhaar_last4: Mapped[str] = mapped_column(
        String(4),
        nullable=False
    )

    full_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )

    date_of_birth: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="Pending",
        nullable=False
    )

    rejection_reason: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True
    )

    user = relationship(
        "User",
        back_populates="kyc_records"
    )

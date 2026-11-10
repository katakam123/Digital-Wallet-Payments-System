
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


class MoneyRequest(Base, TimestampMixin):
    __tablename__ = "money_requests"

    __table_args__ = (
        CheckConstraint(
            "amount > 0",
            name="ck_money_request_amount_positive",
        ),
        CheckConstraint(
            "requester_id != payer_id",
            name="ck_money_request_different_users",
        ),
        CheckConstraint(
            "status IN ('Pending', 'Paid', 'Declined', 'Cancelled', 'Expired')",
            name="ck_money_request_status",
        ),
        Index(
            "ix_money_requests_requester_status",
            "requester_id",
            "status",
        ),
        Index(
            "ix_money_requests_payer_status",
            "payer_id",
            "status",
        ),
        Index(
            "ix_money_requests_expires_at",
            "expires_at",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    requester_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    payer_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    amount = Column(
        Numeric(12, 2),
        nullable=False,
    )

    note = Column(
        String(255),
        nullable=True,
    )

    status = Column(
        String(20),
        nullable=False,
        default="Pending",
    )

    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
    )

    requester = relationship(
        "User",
        foreign_keys=[requester_id],
    )

    payer = relationship(
        "User",
        foreign_keys=[payer_id],
    )

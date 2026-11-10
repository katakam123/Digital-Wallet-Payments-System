from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.base import TimestampMixin


class FraudReview(Base, TimestampMixin):
    __tablename__ = "fraud_reviews"

    __table_args__ = (
        UniqueConstraint(
            "transaction_id",
            name="uq_fraud_review_transaction",
        ),
        Index(
            "ix_fraud_reviews_status_created",
            "status",
            "created_at",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    transaction_id = Column(
        Integer,
        ForeignKey("financial_transactions.id", ondelete="RESTRICT"),
        nullable=False,
    )

    sender_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    receiver_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Why the transaction was flagged.
    flag_reason = Column(Text, nullable=False)

    # Pending, Approved or Rejected.
    status = Column(
        String(20),
        nullable=False,
        default="Pending",
        index=True,
    )

    # Admin decision details.
    admin_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )

    decision_reason = Column(Text, nullable=True)

    decided_at = Column(DateTime(timezone=True), nullable=True)

    transaction = relationship("FinancialTransaction")
    sender = relationship("User", foreign_keys=[sender_user_id])
    receiver = relationship("User", foreign_keys=[receiver_user_id])
    admin = relationship("User", foreign_keys=[admin_id])
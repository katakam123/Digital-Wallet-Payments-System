
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.base import TimestampMixin


class BankAccount(Base, TimestampMixin):
    __tablename__ = "bank_accounts"

    __table_args__ = (
        Index(
            "ix_bank_accounts_user_id",
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

    account_holder_name = Column(
        String(150),
        nullable=False,
    )

    # Full account number is stored internally.
    # API responses must always return only the masked number.
    account_number = Column(
        String(18),
        nullable=False,
    )

    ifsc_code = Column(
        String(11),
        nullable=False,
    )

    bank_name = Column(
        String(150),
        nullable=False,
    )

    is_primary = Column(
        Boolean,
        nullable=False,
        default=False,
    )

    user = relationship(
        "User",
        back_populates="bank_accounts",
    )

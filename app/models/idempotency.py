
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)

from app.database import Base
from app.models.base import TimestampMixin


class IdempotencyRecord(Base, TimestampMixin):
    __tablename__ = "idempotency_records"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "endpoint",
            "idempotency_key",
            name="uq_idempotency_user_endpoint_key",
        ),
        Index(
            "ix_idempotency_expires_at",
            "expires_at",
        ),
        Index(
            "ix_idempotency_status",
            "status",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    endpoint = Column(
        String(255),
        nullable=False,
    )

    idempotency_key = Column(
        String(255),
        nullable=False,
    )

    request_hash = Column(
        String(64),
        nullable=False,
    )

    status = Column(
        String(20),
        nullable=False,
        default="PROCESSING",
        server_default="PROCESSING",
    )

    response_status = Column(
        Integer,
        nullable=True,
    )

    response_body = Column(
        JSON,
        nullable=True,
    )

    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
    )

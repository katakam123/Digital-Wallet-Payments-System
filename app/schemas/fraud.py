from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class FraudDecisionRequest(BaseModel):
    reason: str = Field(
        ...,
        min_length=5,
        max_length=500,
    )


class FraudReviewResponse(BaseModel):
    id: int
    transaction_id: int
    sender_user_id: int
    receiver_user_id: int
    flag_reason: str
    status: str
    admin_id: int | None = None
    decision_reason: str | None = None
    decided_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FlaggedTransactionListResponse(BaseModel):
    total: int
    transactions: list[FraudReviewResponse]
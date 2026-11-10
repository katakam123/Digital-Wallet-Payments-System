
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, ConfigDict


# Request to withdraw money
class WithdrawalCreate(BaseModel):
    bank_account_id: int = Field(
        ...,
        gt=0,
    )

    amount: Decimal = Field(
        ...,
        ge=Decimal("100.00"),
        max_digits=12,
        decimal_places=2,
    )

    pin: str = Field(
        ...,
        min_length=4,
        max_length=4,
    )


# Withdrawal response
class WithdrawalResponse(BaseModel):
    id: int
    transaction_id: int
    bank_account_id: int
    amount: Decimal
    status: str
    processed_at: datetime | None = None
    failure_reason: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# List withdrawals
class WithdrawalListResponse(BaseModel):
    total: int
    withdrawals: list[WithdrawalResponse]

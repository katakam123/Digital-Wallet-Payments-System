
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


# Create a new money request
class MoneyRequestCreate(BaseModel):
    payer_phone: str = Field(
        ...,
        min_length=10,
        max_length=15,
        description="Phone number of the person being asked to pay",
    )

    amount: Decimal = Field(
        ...,
        gt=0,
        max_digits=12,
        decimal_places=2,
    )

    note: Optional[str] = Field(
        default=None,
        max_length=255,
    )


# Pay a money request
class MoneyRequestPay(BaseModel):
    pin: str = Field(
        ...,
        min_length=4,
        max_length=4,
    )

    otp: Optional[str] = Field(
        default=None,
        min_length=6,
        max_length=6,
    )


# Response for a single money request
class MoneyRequestResponse(BaseModel):
    id: int
    requester_id: int
    payer_id: int
    amount: Decimal
    note: Optional[str] = None
    status: str
    expires_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Response after successfully paying a request
class MoneyRequestPaymentResponse(BaseModel):
    message: str
    money_request: MoneyRequestResponse
    transaction_ref: str
    amount: Decimal


# Response after declining or cancelling
class MoneyRequestActionResponse(BaseModel):
    message: str
    money_request: MoneyRequestResponse


# List of money requests
class MoneyRequestListResponse(BaseModel):
    total: int
    requests: list[MoneyRequestResponse]

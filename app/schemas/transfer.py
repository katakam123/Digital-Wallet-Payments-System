
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class TransferRequest(BaseModel):
    receiver_phone: str = Field(
        min_length=10,
        max_length=20
    )
    amount: Decimal = Field(
        gt=0,
        max_digits=12,
        decimal_places=2
    )
    note: Optional[str] = Field(
        default=None,
        max_length=500
    )
    pin: str = Field(
        min_length=4,
        max_length=4,
        pattern=r"^\d{4}$"
    )
    otp: Optional[str] = Field(
        default=None,
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "receiver_phone": "9876543210",
                "amount": "1500.00",
                "note": "Payment for lunch",
                "pin": "4826",
                "otp": "123456"
            }
        }
    )


class TransferResponse(BaseModel):
    transaction_ref: str
    transaction_type: str
    amount: Decimal
    status: str
    sender_wallet_balance: Decimal
    message: str


class TransferDetailsResponse(BaseModel):
    transaction_ref: str
    transaction_type: str
    amount: Decimal
    status: str
    description: Optional[str] = None
    created_at: Optional[str] = None

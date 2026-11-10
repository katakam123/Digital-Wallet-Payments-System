
from decimal import Decimal

from pydantic import BaseModel, Field, ConfigDict


class MerchantPaymentRequest(BaseModel):
    merchant_code: str = Field(
        min_length=5,
        max_length=20,
    )

    amount: Decimal = Field(
        gt=0,
        max_digits=12,
        decimal_places=2,
    )

    pin: str = Field(
        min_length=4,
        max_length=4,
        pattern=r"^\d{4}$",
    )


class MerchantPaymentResponse(BaseModel):
    transaction_ref: str
    status: str
    merchant_code: str
    merchant_name: str
    amount: Decimal
    merchant_fee: Decimal
    merchant_received: Decimal
    cashback_amount: Decimal
    cashback_status: str
    message: str

    model_config = ConfigDict(from_attributes=True)

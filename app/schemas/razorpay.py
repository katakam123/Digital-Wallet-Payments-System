
from decimal import Decimal

from pydantic import BaseModel, Field, ConfigDict


class RazorpayOrderCreate(BaseModel):
    amount: Decimal = Field(
        gt=0,
        le=100000,
        decimal_places=2,
    )


class RazorpayOrderResponse(BaseModel):
    order_id: str
    amount: int
    currency: str
    key_id: str


class RazorpayVerifyRequest(BaseModel):
    razorpay_order_id: str = Field(min_length=5, max_length=100)
    razorpay_payment_id: str = Field(min_length=5, max_length=100)
    razorpay_signature: str = Field(min_length=20, max_length=200)


class RazorpayPaymentResponse(BaseModel):
    id: int
    amount: Decimal
    currency: str
    razorpay_order_id: str
    razorpay_payment_id: str | None
    status: str
    transaction_id: int | None

    model_config = ConfigDict(from_attributes=True)

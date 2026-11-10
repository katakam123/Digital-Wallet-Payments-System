
from decimal import Decimal

from pydantic import BaseModel, Field


class MerchantRefundRequest(BaseModel):
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


class MerchantRefundResponse(BaseModel):
    refund_transaction_ref: str
    original_transaction_ref: str
    status: str
    refund_amount: Decimal
    original_amount: Decimal
    total_refunded: Decimal
    remaining_refundable: Decimal
    cashback_status: str
    message: str

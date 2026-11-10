
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class MerchantPaymentHistoryItem(BaseModel):
    transaction_ref: str
    customer_id: int
    customer_name: str

    amount: Decimal
    merchant_fee: Decimal
    merchant_received: Decimal

    status: str

    refunded_amount: Decimal
    unrefunded_amount: Decimal

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MerchantPaymentHistoryResponse(BaseModel):
    total: int
    skip: int
    limit: int
    payments: list[MerchantPaymentHistoryItem]


from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class MerchantDashboardResponse(BaseModel):
    total_payments: int

    total_sales: Decimal
    total_fees: Decimal
    total_received: Decimal
    total_refunds: Decimal
    net_after_refunds: Decimal

    today_payments: int
    today_sales: Decimal
    today_received: Decimal

    currency: str = "INR"

    model_config = ConfigDict(from_attributes=True)

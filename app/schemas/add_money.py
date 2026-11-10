
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, ConfigDict


class AddMoneyRequest(BaseModel):
    amount: Decimal = Field(
        gt=0,
        max_digits=12,
        decimal_places=2
    )
    source: Literal["UPI", "Card", "Net Banking"]
    simulate_status: Literal["Success", "Failed"] = "Success"

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "amount": "1000.00",
                "source": "UPI",
                "simulate_status": "Success"
            }
        }
    )


class AddMoneyResponse(BaseModel):
    transaction_ref: str
    transaction_type: str
    amount: Decimal
    source: str
    status: str
    wallet_balance: Decimal
    message: str

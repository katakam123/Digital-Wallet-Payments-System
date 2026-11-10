
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, ConfigDict


class BillFetchRequest(BaseModel):
    bill_type: Literal["Mobile Recharge", "Electricity"]

    provider: str = Field(min_length=2, max_length=100)

    customer_identifier: str = Field(
        min_length=6,
        max_length=50,
    )


class BillFetchResponse(BaseModel):
    bill_type: str
    provider: str
    customer_identifier: str
    customer_name: str
    amount: Decimal
    due_date: str
    bill_reference: str


class BillPaymentCreate(BaseModel):
    bill_type: Literal["Mobile Recharge", "Electricity"]

    provider: str = Field(min_length=2, max_length=100)

    customer_identifier: str = Field(
        min_length=6,
        max_length=50,
    )

    amount: Decimal = Field(gt=0)

    bill_reference: str = Field(min_length=5, max_length=100)

    transaction_pin: str = Field(pattern=r"^\d{4}$")


class BillPaymentResponse(BaseModel):
    id: int
    transaction_ref: str
    provider_reference: str
    bill_type: str
    provider: str
    customer_identifier: str
    amount: Decimal
    status: str

    model_config = ConfigDict(from_attributes=True)

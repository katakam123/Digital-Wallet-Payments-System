
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import Numeric


MONEY_TYPE = Numeric(12, 2)


def money(value) -> Decimal:
    amount = Decimal(str(value))

    if not amount.is_finite():
        raise ValueError("Invalid monetary amount")

    return amount.quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )


def validate_positive_amount(value: Decimal) -> Decimal:
    amount = money(value)

    if amount <= Decimal("0.00"):
        raise ValueError("Amount must be greater than zero")

    return amount

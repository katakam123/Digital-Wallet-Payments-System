
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, field_validator
import re


# Request to add a bank account
class BankAccountCreate(BaseModel):
    account_holder_name: str = Field(
        ...,
        min_length=2,
        max_length=150,
    )

    account_number: str = Field(
        ...,
        min_length=9,
        max_length=18,
    )

    ifsc_code: str = Field(
        ...,
        min_length=11,
        max_length=11,
    )

    bank_name: str = Field(
        ...,
        min_length=2,
        max_length=150,
    )

    is_primary: bool = False

    otp: str = Field(
        ...,
        min_length=6,
        max_length=6,
    )

    @field_validator("account_number")
    @classmethod
    def validate_account_number(cls, value):
        if not value.isdigit():
            raise ValueError("Account number must contain only digits.")

        if not 9 <= len(value) <= 18:
            raise ValueError(
                "Account number must contain 9 to 18 digits."
            )

        return value

    @field_validator("ifsc_code")
    @classmethod
    def validate_ifsc_code(cls, value):
        value = value.upper()

        if not re.fullmatch(r"[A-Z]{4}0[A-Z0-9]{6}", value):
            raise ValueError(
                "Invalid IFSC code. Example: SBIN0001234."
            )

        return value

    @field_validator("otp")
    @classmethod
    def validate_otp(cls, value):
        if not value.isdigit():
            raise ValueError("OTP must contain exactly 6 digits.")

        return value


# Safe bank account response
class BankAccountResponse(BaseModel):
    id: int
    account_holder_name: str
    masked_account_number: str
    ifsc_code: str
    bank_name: str
    is_primary: bool
    created_at: datetime


# List bank accounts
class BankAccountListResponse(BaseModel):
    total: int
    bank_accounts: list[BankAccountResponse]

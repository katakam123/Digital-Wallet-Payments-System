
from datetime import date
from typing import Optional

from pydantic import (
    BaseModel,
    Field,
    ConfigDict,
    field_validator
)
import re


class KYCSubmitSchema(BaseModel):

    pan_number: str = Field(
        min_length=10,
        max_length=10
    )

    aadhaar_last4: str = Field(
        min_length=4,
        max_length=4
    )

    full_name: str = Field(
        min_length=2,
        max_length=150
    )

    date_of_birth: date

    @field_validator("pan_number")
    @classmethod
    def validate_pan(cls, value):

        value = value.strip().upper()

        if not re.fullmatch(
            r"[A-Z]{5}[0-9]{4}[A-Z]",
            value
        ):
            raise ValueError(
                "Invalid PAN format. Example: ABCDE1234F"
            )

        return value

    @field_validator("aadhaar_last4")
    @classmethod
    def validate_aadhaar(cls, value):

        if not re.fullmatch(r"[0-9]{4}", value):
            raise ValueError(
                "Aadhaar last four digits must contain exactly 4 digits"
            )

        return value

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, value):

        if value >= date.today():
            raise ValueError(
                "Date of birth must be in the past"
            )

        return value


class KYCReviewSchema(BaseModel):

    rejection_reason: Optional[str] = Field(
        default=None,
        max_length=500
    )


class KYCResponse(BaseModel):

    id: int
    user_id: int
    pan_number: str
    aadhaar_last4: str
    full_name: str
    date_of_birth: date
    status: str
    rejection_reason: Optional[str]

    model_config = ConfigDict(
        from_attributes=True
    )


class KYCFreezeSchema(BaseModel):

    reason: str = Field(
        min_length=5,
        max_length=500
    )

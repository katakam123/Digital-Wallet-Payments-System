
from typing import Literal, Optional

from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    ConfigDict,
    model_validator
)


class RegisterSchema(BaseModel):

    full_name: str = Field(
        min_length=2,
        max_length=150
    )

    email: EmailStr

    phone: Optional[str] = Field(
        default=None,
        max_length=20
    )

    password: str = Field(
        min_length=8,
        max_length=72
    )

    role: Literal["User", "Merchant"] = "User"

    business_name: Optional[str] = Field(
        default=None,
        max_length=150
    )

    business_category: Optional[str] = Field(
        default=None,
        max_length=100
    )

    @model_validator(mode="after")
    def validate_merchant(self):

        if self.role == "Merchant":

            if not self.business_name:
                raise ValueError(
                    "business_name is required for merchants"
                )

            if not self.business_category:
                raise ValueError(
                    "business_category is required for merchants"
                )

        elif self.business_name or self.business_category:
            raise ValueError(
                "Business information is only allowed for merchants"
            )

        return self


class UserResponse(BaseModel):

    id: int
    full_name: str
    email: EmailStr
    phone: Optional[str]

    role: str

    business_name: Optional[str]
    business_category: Optional[str]

    is_active: bool
    kyc_status: str

    model_config = ConfigDict(
        from_attributes=True
    )


class TokenResponse(BaseModel):

    access_token: str
    token_type: str
    expires_in: int
    user: UserResponse

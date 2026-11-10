import re

from typing import Literal
from pydantic import BaseModel, Field, field_validator


OTP_PURPOSES = (
    "High Value Transfer",
    "Add Bank Account",
    "PIN Reset",
)


def validate_pin(pin: str) -> str:
    if not re.fullmatch(r"\d{4}", pin):
        raise ValueError("PIN must contain exactly 4 digits.")

    if pin in {
        "1234", "4321", "1111", "2222", "3333",
        "4444", "5555", "6666", "7777", "8888",
        "9999", "0000", "1212", "1122",
    }:
        raise ValueError("This PIN is too simple. Choose another PIN.")

    return pin


class SetPINSchema(BaseModel):
    pin: str

    @field_validator("pin")
    @classmethod
    def check_pin(cls, value):
        return validate_pin(value)


class ChangePINSchema(BaseModel):
    old_pin: str
    new_pin: str

    @field_validator("new_pin")
    @classmethod
    def check_new_pin(cls, value):
        return validate_pin(value)


class ResetPINSchema(BaseModel):
    new_pin: str

    @field_validator("new_pin")
    @classmethod
    def check_new_pin(cls, value):
        return validate_pin(value)


class OTPSendSchema(BaseModel):
    purpose: Literal[
        "High Value Transfer",
        "Add Bank Account",
        "PIN Reset",
    ]


class OTPVerifySchema(BaseModel):
    purpose: Literal[
        "High Value Transfer",
        "Add Bank Account",
        "PIN Reset",
    ]

    otp: str = Field(pattern=r"^\d{6}$")
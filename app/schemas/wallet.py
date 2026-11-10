
from decimal import Decimal
from pydantic import BaseModel, ConfigDict


class WalletResponse(BaseModel):

    id: int
    owner_id: int
    wallet_number: str
    balance: Decimal
    currency: str
    kyc_level: str
    status: str
    freeze_reason: str | None

    model_config = ConfigDict(
        from_attributes=True
    )

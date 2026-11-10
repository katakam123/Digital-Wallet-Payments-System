
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.wallet import Wallet
from app.models.user import User

from app.schemas.wallet import WalletResponse
from app.schemas.add_money import AddMoneyRequest, AddMoneyResponse

from app.auth.security import require_user_or_merchant
from app.services.add_money_service import add_money


router = APIRouter(
    prefix="/wallet",
    tags=["Wallet"],
)


# GET WALLET DETAILS
@router.get(
    "",
    response_model=WalletResponse,
)
def get_wallet(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_or_merchant),
):
    wallet = (
        db.query(Wallet)
        .filter(Wallet.owner_id == current_user.id)
        .first()
    )

    if not wallet:
        raise HTTPException(
            status_code=404,
            detail="Wallet not found.",
        )

    return wallet


# ADD MONEY
@router.post(
    "/add-money",
    response_model=AddMoneyResponse,
)
def add_money_to_wallet(
    request: AddMoneyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_or_merchant),
):
    return add_money(
        db=db,
        current_user=current_user,
        amount=request.amount,
        source=request.source,
        simulate_status=request.simulate_status,
    )

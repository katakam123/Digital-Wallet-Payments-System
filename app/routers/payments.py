
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User

from app.auth.security import require_user_or_merchant

from app.schemas.merchant_payment import (
    MerchantPaymentRequest,
    MerchantPaymentResponse,
)

from app.services.merchant_payment_service import (
    execute_merchant_payment,
)


router = APIRouter(
    prefix="/payments",
    tags=["Payments"],
)


@router.post(
    "/merchant",
    response_model=MerchantPaymentResponse,
)
def pay_merchant(
    request: MerchantPaymentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_or_merchant),
):
    return execute_merchant_payment(
        db=db,
        current_user=current_user,
        merchant_code=request.merchant_code,
        amount=request.amount,
        pin=request.pin,
    )

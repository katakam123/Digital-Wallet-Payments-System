
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User

from app.auth.security import require_user_or_merchant

from app.schemas.merchant_refund import (
    MerchantRefundRequest,
    MerchantRefundResponse,
)

from app.services.merchant_refund_service import (
    execute_merchant_refund,
)


router = APIRouter(
    prefix="/payments",
    tags=["Merchant Refunds"],
)


@router.post(
    "/{transaction_ref}/refund",
    response_model=MerchantRefundResponse,
)
def refund_merchant_payment(
    transaction_ref: str,
    request: MerchantRefundRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_or_merchant),
):
    return execute_merchant_refund(
        db=db,
        current_user=current_user,
        transaction_ref=transaction_ref,
        amount=request.amount,
        pin=request.pin,
    )

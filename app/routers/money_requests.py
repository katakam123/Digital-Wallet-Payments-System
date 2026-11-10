
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.auth.security import require_user_or_merchant

from app.schemas.money_request import (
    MoneyRequestCreate,
    MoneyRequestPay,
    MoneyRequestResponse,
    MoneyRequestPaymentResponse,
    MoneyRequestActionResponse,
    MoneyRequestListResponse,
)

from app.services.money_request_service import (
    create_money_request,
    get_money_requests,
    pay_money_request,
    decline_money_request,
    cancel_money_request,
)


router = APIRouter(
    prefix="/money-requests",
    tags=["Money Requests"],
)


# 1. CREATE MONEY REQUEST
@router.post(
    "",
    response_model=MoneyRequestResponse,
    status_code=201,
)
def create_request(
    request: MoneyRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_or_merchant),
):
    return create_money_request(
        db=db,
        current_user=current_user,
        payer_phone=request.payer_phone,
        amount=request.amount,
        note=request.note,
    )


# 2. GET MONEY REQUESTS
@router.get(
    "",
    response_model=MoneyRequestListResponse,
)
def list_requests(
    direction: str = Query(
        default="all",
        description="all, incoming, or outgoing",
    ),
    status: Optional[str] = Query(
        default=None,
        description="Pending, Paid, Declined, Cancelled, or Expired",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_or_merchant),
):
    return get_money_requests(
        db=db,
        current_user=current_user,
        direction=direction,
        status=status,
    )


# 3. PAY MONEY REQUEST
@router.put(
    "/{request_id}/pay",
    response_model=MoneyRequestPaymentResponse,
)
def pay_request(
    request_id: int,
    request: MoneyRequestPay,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_or_merchant),
):
    return pay_money_request(
        db=db,
        current_user=current_user,
        request_id=request_id,
        pin=request.pin,
        otp=request.otp,
    )


# 4. DECLINE MONEY REQUEST
@router.put(
    "/{request_id}/decline",
    response_model=MoneyRequestActionResponse,
)
def decline_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_or_merchant),
):
    return decline_money_request(
        db=db,
        current_user=current_user,
        request_id=request_id,
    )


# 5. CANCEL MONEY REQUEST
@router.put(
    "/{request_id}/cancel",
    response_model=MoneyRequestActionResponse,
)
def cancel_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_or_merchant),
):
    return cancel_money_request(
        db=db,
        current_user=current_user,
        request_id=request_id,
    )

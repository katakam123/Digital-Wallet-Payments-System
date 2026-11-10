
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.razorpay import (
    RazorpayOrderCreate,
    RazorpayOrderResponse,
)
from app.services.razorpay_service import create_razorpay_order

# Use the same authentication dependency as your existing routers.
from app.auth.security import get_current_user

router = APIRouter(
    prefix="/razorpay",
    tags=["Razorpay Test Payments"],
)


@router.post(
    "/create-order",
    response_model=RazorpayOrderResponse,
)
def create_order(
    request: RazorpayOrderCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return create_razorpay_order(
        db=db,
        current_user=current_user,
        amount=request.amount,
    )

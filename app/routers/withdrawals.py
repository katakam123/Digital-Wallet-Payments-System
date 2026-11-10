from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.auth.security import require_user_or_merchant

from app.schemas.withdrawal import (
    WithdrawalCreate,
    WithdrawalResponse,
    WithdrawalListResponse,
)

from app.services.withdrawal_service import (
    create_withdrawal,
    get_withdrawals,
)


router = APIRouter(
    prefix="/withdrawals",
    tags=["Withdrawals"],
)


@router.post(
    "",
    response_model=WithdrawalResponse,
    status_code=201,
)
def request_withdrawal(
    request: WithdrawalCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_or_merchant),
):
    return create_withdrawal(
        db=db,
        current_user=current_user,
        request=request,
    )


@router.get(
    "",
    response_model=WithdrawalListResponse,
)
def list_withdrawals(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_or_merchant),
):
    return get_withdrawals(
        db=db,
        current_user=current_user,
    )
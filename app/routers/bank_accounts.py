from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.auth.security import require_user_or_merchant

from app.schemas.bank_account import (
    BankAccountCreate,
    BankAccountResponse,
    BankAccountListResponse,
)

from app.services.bank_account_service import (
    add_bank_account,
    get_bank_accounts,
    delete_bank_account,
)

router = APIRouter(
    prefix="/bank-accounts",
    tags=["Bank Accounts"],
)


@router.post(
    "",
    response_model=BankAccountResponse,
    status_code=201,
)
def create_bank_account(
    request: BankAccountCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_or_merchant),
):
    return add_bank_account(
        db=db,
        current_user=current_user,
        request=request,
    )


@router.get(
    "",
    response_model=BankAccountListResponse,
)
def list_bank_accounts(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_or_merchant),
):
    return get_bank_accounts(
        db=db,
        current_user=current_user,
    )


@router.delete("/{bank_account_id}")
def remove_bank_account(
    bank_account_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_or_merchant),
):
    return delete_bank_account(
        db=db,
        current_user=current_user,
        bank_account_id=bank_account_id,
    )
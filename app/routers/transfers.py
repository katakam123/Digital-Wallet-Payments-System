
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db

from app.models.user import User
from app.models.financial_transaction import FinancialTransaction
from app.models.ledger_entry import LedgerEntry
from app.models.ledger_account import LedgerAccount
from app.models.wallet import Wallet

from app.auth.security import require_user_or_merchant

from app.schemas.transfer import (
    TransferRequest,
    TransferResponse,
    TransferDetailsResponse,
)

from app.services.transfer_service import execute_transfer


router = APIRouter(
    prefix="/transfers",
    tags=["Transfers"],
)


# SEND MONEY
@router.post(
    "",
    response_model=TransferResponse,
)
def send_money(
    request: TransferRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_or_merchant),
):
    return execute_transfer(
        db=db,
        current_user=current_user,
        receiver_phone=request.receiver_phone,
        amount=request.amount,
        note=request.note,
        pin=request.pin,
        otp=request.otp,
    )


# GET TRANSFER DETAILS
@router.get(
    "/{transaction_ref}",
    response_model=TransferDetailsResponse,
)
def get_transfer_details(
    transaction_ref: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_or_merchant),
):
    transaction = (
        db.query(FinancialTransaction)
        .filter(
            FinancialTransaction.transaction_ref == transaction_ref,
            FinancialTransaction.type == "Transfer",
        )
        .first()
    )

    if not transaction:
        raise HTTPException(
            status_code=404,
            detail="Transfer transaction not found.",
        )

    is_sender = (
        transaction.initiated_by == current_user.id
    )

    is_receiver = (
        db.query(LedgerEntry.id)
        .join(
            LedgerAccount,
            LedgerEntry.account_id == LedgerAccount.id,
        )
        .join(
            Wallet,
            LedgerAccount.wallet_id == Wallet.id,
        )
        .filter(
            LedgerEntry.transaction_id == transaction.id,
            Wallet.owner_id == current_user.id,
            LedgerEntry.entry_type == "Credit",
        )
        .first()
        is not None
    )

    if not is_sender and not is_receiver:
        raise HTTPException(
            status_code=403,
            detail="You are not allowed to view this transfer.",
        )

    return {
        "transaction_ref": transaction.transaction_ref,
        "transaction_type": transaction.type,
        "amount": transaction.amount,
        "status": transaction.status,
        "description": transaction.description,
        "created_at": (
            transaction.created_at.isoformat()
            if transaction.created_at
            else None
        ),
    }

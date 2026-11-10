
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.security import require_user_or_merchant

from app.models.user import User
from app.models.wallet import Wallet
from app.models.ledger_account import LedgerAccount
from app.models.ledger_entry import LedgerEntry
from app.models.financial_transaction import FinancialTransaction

from app.schemas.merchant_payment_history import (
    MerchantPaymentHistoryItem,
    MerchantPaymentHistoryResponse,
)


router = APIRouter(
    prefix="/merchants",
    tags=["Merchant Payment History"],
)


ZERO = Decimal("0.00")


@router.get(
    "/me/payments",
    response_model=MerchantPaymentHistoryResponse,
)
def get_merchant_payment_history(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_or_merchant),
):
    """
    Get payment history for the authenticated merchant.

    Merchants can only view payments received by their own wallet.
    """

    # ------------------------------------------
    # 1. Verify merchant account
    # ------------------------------------------

    if current_user.role != "Merchant":
        raise HTTPException(
            status_code=403,
            detail="Only merchants can access payment history.",
        )

    if not current_user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Your merchant account is inactive.",
        )

    # ------------------------------------------
    # 2. Get merchant wallet
    # ------------------------------------------

    merchant_wallet = (
        db.query(Wallet)
        .filter(
            Wallet.owner_id == current_user.id
        )
        .first()
    )

    if not merchant_wallet:
        raise HTTPException(
            status_code=404,
            detail="Merchant wallet not found.",
        )

    # ------------------------------------------
    # 3. Get merchant ledger account
    # ------------------------------------------

    merchant_account = (
        db.query(LedgerAccount)
        .filter(
            LedgerAccount.wallet_id == merchant_wallet.id,
            LedgerAccount.account_type == "Merchant Wallet",
        )
        .first()
    )

    # A merchant without a ledger account has no
    # recorded merchant payments yet.
    if not merchant_account:
        return MerchantPaymentHistoryResponse(
            total=0,
            skip=skip,
            limit=limit,
            payments=[],
        )

    # ------------------------------------------
    # 4. Base query for incoming payments
    # ------------------------------------------

    base_query = (
        db.query(
            FinancialTransaction,
            LedgerEntry.amount.label("merchant_received"),
            User.id.label("customer_id"),
            User.full_name.label("customer_name"),
        )
        .join(
            LedgerEntry,
            LedgerEntry.transaction_id == FinancialTransaction.id,
        )
        .join(
            User,
            User.id == FinancialTransaction.initiated_by,
        )
        .filter(
            FinancialTransaction.type == "Merchant Payment",
            LedgerEntry.account_id == merchant_account.id,
            LedgerEntry.entry_type == "Credit",
        )
    )

    # ------------------------------------------
    # 5. Total number of matching payments
    # ------------------------------------------

    total = base_query.count()

    # ------------------------------------------
    # 6. Fetch paginated payments
    # ------------------------------------------

    rows = (
        base_query
        .order_by(FinancialTransaction.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    payments = []

    # ------------------------------------------
    # 7. Calculate refund totals
    # ------------------------------------------

    for row in rows:

        transaction = row[0]

        merchant_received = Decimal(
            str(row.merchant_received)
        )

        original_amount = Decimal(
            str(transaction.amount)
        )

        merchant_fee = original_amount - merchant_received

        refunded_amount = (
            db.query(
                func.coalesce(
                    func.sum(FinancialTransaction.amount),
                    0,
                )
            )
            .filter(
                FinancialTransaction.type == "Merchant Refund",
                FinancialTransaction.related_transaction_id
                == transaction.id,
                FinancialTransaction.status == "Success",
            )
            .scalar()
        )

        refunded_amount = Decimal(
            str(refunded_amount)
        ).quantize(Decimal("0.01"))

        unrefunded_amount = max(
            ZERO,
            original_amount - refunded_amount,
        )

        payments.append(
            MerchantPaymentHistoryItem(
                transaction_ref=transaction.transaction_ref,
                customer_id=row.customer_id,
                customer_name=row.customer_name,
                amount=original_amount,
                merchant_fee=merchant_fee,
                merchant_received=merchant_received,
                status=transaction.status,
                refunded_amount=refunded_amount,
                unrefunded_amount=unrefunded_amount,
                created_at=transaction.created_at,
            )
        )

    # ------------------------------------------
    # 8. Return response
    # ------------------------------------------

    return MerchantPaymentHistoryResponse(
        total=total,
        skip=skip,
        limit=limit,
        payments=payments,
    )

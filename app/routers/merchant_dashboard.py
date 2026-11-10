
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.security import require_user_or_merchant

from app.models.user import User
from app.models.wallet import Wallet
from app.models.ledger_account import LedgerAccount
from app.models.ledger_entry import LedgerEntry
from app.models.financial_transaction import FinancialTransaction

from app.schemas.merchant_dashboard import (
    MerchantDashboardResponse,
)


router = APIRouter(
    prefix="/merchants",
    tags=["Merchant Dashboard"],
)

ZERO = Decimal("0.00")
CENT = Decimal("0.01")

PAYMENT_STATUSES = (
    "Success",
    "Partially Refunded",
    "Refunded",
)


def to_decimal(value):
    if value is None:
        return ZERO

    return Decimal(str(value)).quantize(CENT)


@router.get(
    "/me/dashboard",
    response_model=MerchantDashboardResponse,
)
def get_merchant_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_or_merchant),
):
    """
    Return sales and payment statistics for the logged-in merchant.
    """

    # ------------------------------------------
    # 1. Validate merchant
    # ------------------------------------------

    if current_user.role != "Merchant":
        raise HTTPException(
            status_code=403,
            detail="Only merchants can access this dashboard.",
        )

    if not current_user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Your merchant account is inactive.",
        )

    # ------------------------------------------
    # 2. Find merchant wallet
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
    # 3. Find merchant ledger account
    # ------------------------------------------

    merchant_account = (
        db.query(LedgerAccount)
        .filter(
            LedgerAccount.wallet_id == merchant_wallet.id,
            LedgerAccount.account_type == "Merchant Wallet",
        )
        .first()
    )

    if not merchant_account:
        return MerchantDashboardResponse(
            total_payments=0,
            total_sales=ZERO,
            total_fees=ZERO,
            total_received=ZERO,
            total_refunds=ZERO,
            net_after_refunds=ZERO,
            today_payments=0,
            today_sales=ZERO,
            today_received=ZERO,
        )

    # ------------------------------------------
    # 4. Subquery: successful refunds
    # ------------------------------------------

    refund_totals = (
        db.query(
            FinancialTransaction.related_transaction_id.label(
                "payment_id"
            ),
            func.sum(
                FinancialTransaction.amount
            ).label("refunded_amount"),
        )
        .filter(
            FinancialTransaction.type == "Merchant Refund",
            FinancialTransaction.status == "Success",
            FinancialTransaction.related_transaction_id.isnot(None),
        )
        .group_by(
            FinancialTransaction.related_transaction_id
        )
        .subquery()
    )

    # ------------------------------------------
    # 5. Base payment query
    # ------------------------------------------

    base_query = (
        db.query(
            FinancialTransaction.id.label("payment_id"),
            FinancialTransaction.amount.label("sale_amount"),
            FinancialTransaction.created_at.label("created_at"),
            LedgerEntry.amount.label("merchant_received"),
            func.coalesce(
                refund_totals.c.refunded_amount,
                0,
            ).label("refunded_amount"),
        )
        .join(
            LedgerEntry,
            LedgerEntry.transaction_id == FinancialTransaction.id,
        )
        .outerjoin(
            refund_totals,
            refund_totals.c.payment_id == FinancialTransaction.id,
        )
        .filter(
            FinancialTransaction.type == "Merchant Payment",
            FinancialTransaction.status.in_(PAYMENT_STATUSES),
            LedgerEntry.account_id == merchant_account.id,
            LedgerEntry.entry_type == "Credit",
        )
    )

    # ------------------------------------------
    # 6. Calculate overall statistics
    # ------------------------------------------

    overall = (
        db.query(
            func.count(base_query.subquery().c.payment_id),
            func.coalesce(
                func.sum(base_query.subquery().c.sale_amount),
                0,
            ),
            func.coalesce(
                func.sum(base_query.subquery().c.merchant_received),
                0,
            ),
            func.coalesce(
                func.sum(base_query.subquery().c.refunded_amount),
                0,
            ),
        )
        .first()
    )

    total_payments = int(overall[0] or 0)
    total_sales = to_decimal(overall[1])
    total_received = to_decimal(overall[2])
    total_refunds = to_decimal(overall[3])

    total_fees = (
        total_sales - total_received
    ).quantize(CENT)

    net_after_refunds = (
        total_received - total_refunds
    ).quantize(CENT)

    # ------------------------------------------
    # 7. Calculate today's statistics
    # ------------------------------------------

    today = datetime.now(timezone.utc).date()

    today_query = base_query.filter(
        func.date(
            FinancialTransaction.created_at
        ) == today
    )

    today_result = (
        db.query(
            func.count(today_query.subquery().c.payment_id),
            func.coalesce(
                func.sum(today_query.subquery().c.sale_amount),
                0,
            ),
            func.coalesce(
                func.sum(today_query.subquery().c.merchant_received),
                0,
            ),
        )
        .first()
    )

    today_payments = int(today_result[0] or 0)
    today_sales = to_decimal(today_result[1])
    today_received = to_decimal(today_result[2])

    # ------------------------------------------
    # 8. Return dashboard
    # ------------------------------------------

    return MerchantDashboardResponse(
        total_payments=total_payments,
        total_sales=total_sales,
        total_fees=total_fees,
        total_received=total_received,
        total_refunds=total_refunds,
        net_after_refunds=net_after_refunds,
        today_payments=today_payments,
        today_sales=today_sales,
        today_received=today_received,
        currency="INR",
    )

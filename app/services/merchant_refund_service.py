
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.wallet import Wallet
from app.models.ledger_account import LedgerAccount
from app.models.ledger_entry import LedgerEntry
from app.models.financial_transaction import FinancialTransaction
from app.models.cashback import Cashback

from app.services.ledger_service import (
    money,
    post_transaction,
)

from app.services.pin_otp_service import (
    verify_transaction_pin_for_payment,
)


ZERO = Decimal("0.00")
REFUND_WINDOW_DAYS = 7


def execute_merchant_refund(
    db: Session,
    current_user: User,
    transaction_ref: str,
    amount: Decimal,
    pin: str,
):
    try:
        amount = money(amount)

        if amount <= ZERO:
            raise HTTPException(
                status_code=400,
                detail="Refund amount must be greater than zero.",
            )

        # -----------------------------------------
        # 1. Lock and validate merchant
        # -----------------------------------------

        merchant = (
            db.query(User)
            .filter(User.id == current_user.id)
            .with_for_update()
            .first()
        )

        if not merchant or merchant.role != "Merchant":
            raise HTTPException(
                status_code=403,
                detail="Only merchants can process refunds.",
            )

        if not merchant.is_active:
            raise HTTPException(
                status_code=403,
                detail="Merchant account is inactive.",
            )

        # -----------------------------------------
        # 2. Verify merchant transaction PIN
        # -----------------------------------------

        verify_transaction_pin_for_payment(
            db=db,
            user=merchant,
            pin=pin,
        )

        # -----------------------------------------
        # 3. Find and lock original payment
        # -----------------------------------------

        original_payment = (
            db.query(FinancialTransaction)
            .filter(
                FinancialTransaction.transaction_ref
                == transaction_ref,
                FinancialTransaction.type == "Merchant Payment",
            )
            .with_for_update()
            .first()
        )

        if not original_payment:
            raise HTTPException(
                status_code=404,
                detail="Original merchant payment not found.",
            )

        if original_payment.status not in (
            "Success",
            "Partially Refunded",
        ):
            raise HTTPException(
                status_code=409,
                detail="This payment is not eligible for a refund.",
            )

        # -----------------------------------------
        # 4. Check seven-day refund window
        # -----------------------------------------

        created_at = original_payment.created_at

        if created_at.tzinfo is None:
            created_at = created_at.replace(
                tzinfo=timezone.utc
            )

        now = datetime.now(timezone.utc)

        if now > created_at + timedelta(
            days=REFUND_WINDOW_DAYS
        ):
            raise HTTPException(
                status_code=400,
                detail="Refund period of seven days has expired.",
            )

        # -----------------------------------------
        # 5. Identify original customer and merchant
        # -----------------------------------------

        original_entries = (
            db.query(
                LedgerEntry.entry_type,
                LedgerAccount.account_type,
                LedgerAccount.wallet_id,
            )
            .join(
                LedgerAccount,
                LedgerAccount.id == LedgerEntry.account_id,
            )
            .filter(
                LedgerEntry.transaction_id == original_payment.id,
                LedgerAccount.wallet_id.isnot(None),
            )
            .all()
        )

        customer_wallet_id = None
        merchant_wallet_id = None

        for entry_type, account_type, wallet_id in original_entries:

            if (
                entry_type == "Debit"
                and account_type == "User Wallet"
            ):
                customer_wallet_id = wallet_id

            elif (
                entry_type == "Credit"
                and account_type == "Merchant Wallet"
            ):
                merchant_wallet_id = wallet_id

        if not customer_wallet_id or not merchant_wallet_id:
            raise HTTPException(
                status_code=500,
                detail="Could not identify original payment wallets.",
            )

        original_merchant_wallet = (
            db.query(Wallet)
            .filter(Wallet.id == merchant_wallet_id)
            .first()
        )

        if not original_merchant_wallet:
            raise HTTPException(
                status_code=404,
                detail="Original merchant wallet not found.",
            )

        if original_merchant_wallet.owner_id != merchant.id:
            raise HTTPException(
                status_code=403,
                detail="You cannot refund another merchant's payment.",
            )

        customer_wallet = (
            db.query(Wallet)
            .filter(Wallet.id == customer_wallet_id)
            .first()
        )

        if not customer_wallet:
            raise HTTPException(
                status_code=404,
                detail="Original customer wallet not found.",
            )

        # -----------------------------------------
        # 6. Lock pending cashback before wallet locks
        # -----------------------------------------

        cashback = (
            db.query(Cashback)
            .filter(
                Cashback.payment_transaction_id
                == original_payment.id,
            )
            .with_for_update()
            .first()
        )

        # -----------------------------------------
        # 7. Calculate previous refunds
        # -----------------------------------------

        previous_refunds = (
            db.query(
                func.coalesce(
                    func.sum(FinancialTransaction.amount),
                    ZERO,
                )
            )
            .filter(
                FinancialTransaction.related_transaction_id
                == original_payment.id,
                FinancialTransaction.type == "Merchant Refund",
                FinancialTransaction.status == "Success",
            )
            .scalar()
        )

        total_refunded_before = money(previous_refunds)
        original_amount = money(original_payment.amount)

        remaining_refundable = (
            original_amount - total_refunded_before
        )

        if amount > remaining_refundable:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Refund exceeds remaining refundable amount.",
                    "original_amount": str(original_amount),
                    "already_refunded": str(total_refunded_before),
                    "remaining_refundable": str(remaining_refundable),
                },
            )

        # -----------------------------------------
        # 8. Get merchant and customer ledger accounts
        # -----------------------------------------

        merchant_account = (
            db.query(LedgerAccount)
            .filter(
                LedgerAccount.wallet_id == merchant_wallet_id,
                LedgerAccount.account_type == "Merchant Wallet",
            )
            .first()
        )

        customer_account = (
            db.query(LedgerAccount)
            .filter(
                LedgerAccount.wallet_id == customer_wallet_id,
                LedgerAccount.account_type == "User Wallet",
            )
            .first()
        )

        if not merchant_account or not customer_account:
            raise HTTPException(
                status_code=409,
                detail="Refund ledger accounts are not initialized.",
            )

        if original_merchant_wallet.status != "Active":
            raise HTTPException(
                status_code=403,
                detail="Merchant wallet is not active.",
            )

        if customer_wallet.status not in ("Active", "Frozen"):
            raise HTTPException(
                status_code=403,
                detail="Customer wallet cannot receive this refund.",
            )

        # -----------------------------------------
        # 9. Post merchant refund
        # -----------------------------------------

        refund_transaction = post_transaction(
            db=db,
            initiated_by=merchant.id,
            transaction_type="Merchant Refund",
            amount=amount,
            postings=[
                (
                    merchant_account.id,
                    "Debit",
                    amount,
                ),
                (
                    customer_account.id,
                    "Credit",
                    amount,
                ),
            ],
            description=(
                f"Refund for original payment "
                f"{original_payment.transaction_ref}"
            ),
            related_transaction_id=original_payment.id,
            commit=False,
        )

        # -----------------------------------------
        # 10. Update refund totals and original status
        # -----------------------------------------

        total_refunded = total_refunded_before + amount

        if total_refunded == original_amount:
            original_payment.status = "Refunded"
        else:
            original_payment.status = "Partially Refunded"

        remaining_after_refund = (
            original_amount - total_refunded
        )

        # -----------------------------------------
        # 11. Cancel pending cashback
        # -----------------------------------------

        cashback_status = "Not Available"

        if cashback:
            if cashback.status == "Pending":
                cashback.status = "Cancelled"

            cashback_status = cashback.status

        # -----------------------------------------
        # 12. Commit everything atomically
        # -----------------------------------------

        db.commit()
        db.refresh(refund_transaction)

        return {
            "refund_transaction_ref": (
                refund_transaction.transaction_ref
            ),
            "original_transaction_ref": (
                original_payment.transaction_ref
            ),
            "status": refund_transaction.status,
            "refund_amount": amount,
            "original_amount": original_amount,
            "total_refunded": total_refunded,
            "remaining_refundable": remaining_after_refund,
            "cashback_status": cashback_status,
            "message": "Merchant refund processed successfully.",
        }

    except Exception:
        db.rollback()
        raise

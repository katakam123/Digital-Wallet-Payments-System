from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.wallet import Wallet
from app.models.bank_account import BankAccount
from app.models.withdrawal import Withdrawal
from app.models.financial_transaction import FinancialTransaction
from app.models.ledger_entry import LedgerEntry

from app.schemas.withdrawal import WithdrawalCreate

from app.services.ledger_service import (
    money,
    get_system_account,
    get_or_create_wallet_account,
    post_transaction,
)

from app.services.transfer_service import check_spending_limits

from app.services.pin_otp_service import (
    verify_transaction_pin_for_payment,
)


ZERO = Decimal("0.00")
MINIMUM_WITHDRAWAL = Decimal("100.00")


def utc_now():
    return datetime.now(timezone.utc)


def create_withdrawal(
    db: Session,
    current_user: User,
    request: WithdrawalCreate,
):
    # Lock the user row before verifying the transaction PIN.
    user = (
        db.query(User)
        .filter(User.id == current_user.id)
        .with_for_update()
        .first()
    )

    if not user or not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Your account is not active.",
        )

    # Lock the user's wallet.
    wallet = (
        db.query(Wallet)
        .filter(Wallet.owner_id == user.id)
        .with_for_update()
        .first()
    )

    if not wallet:
        raise HTTPException(
            status_code=404,
            detail="Wallet not found.",
        )

    if wallet.status != "Active":
        raise HTTPException(
            status_code=403,
            detail="Your wallet is not active. Withdrawals are not allowed.",
        )

    if wallet.kyc_level != "Full":
        raise HTTPException(
            status_code=403,
            detail="Full KYC verification is required for withdrawals.",
        )

    # Validate withdrawal amount.
    try:
        amount = money(request.amount)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid withdrawal amount.",
        )

    if amount < MINIMUM_WITHDRAWAL:
        raise HTTPException(
            status_code=400,
            detail="Minimum withdrawal amount is ₹100.",
        )

    if money(wallet.balance) < amount:
        raise HTTPException(
            status_code=400,
            detail="Insufficient wallet balance.",
        )

    # Verify that the selected bank account belongs to this user.
    bank_account = (
        db.query(BankAccount)
        .filter(
            BankAccount.id == request.bank_account_id,
            BankAccount.user_id == user.id,
        )
        .with_for_update()
        .first()
    )

    if not bank_account:
        raise HTTPException(
            status_code=404,
            detail="Bank account not found.",
        )

    # Check daily and monthly outgoing transaction limits.
    # Withdrawal is already included in the outgoing transaction types
    # in your transfer service.
    check_spending_limits(
        db=db,
        current_user=user,
        amount=amount,
    )

    # Verify the PIN. The user row is already locked.
    # This function does not commit after successful verification.
    verify_transaction_pin_for_payment(
        db=db,
        user=user,
        pin=request.pin,
    )

    role = getattr(user.role, "value", user.role)

    wallet_account_type = (
        "Merchant Wallet"
        if role == "Merchant"
        else "User Wallet"
    )

    wallet_ledger = get_or_create_wallet_account(
        db=db,
        wallet=wallet,
        account_type=wallet_account_type,
    )

    clearing_account = get_system_account(
        db=db,
        system_code="WITHDRAWAL_CLEARING",
    )

    try:
        # Move wallet funds into Withdrawal Clearing.
        transaction = post_transaction(
            db=db,
            initiated_by=user.id,
            transaction_type="Withdrawal",
            amount=amount,
            postings=[
                (
                    wallet_ledger.id,
                    "Debit",
                    amount,
                ),
                (
                    clearing_account.id,
                    "Credit",
                    amount,
                ),
            ],
            description=(
                f"Withdrawal requested to bank account "
                f"{bank_account.account_number[-4:]}"
            ),
            commit=False,
        )

        withdrawal = Withdrawal(
            user_id=user.id,
            transaction_id=transaction.id,
            bank_account_id=bank_account.id,
            amount=amount,
            status="Pending",
        )

        db.add(withdrawal)
        db.commit()
        db.refresh(withdrawal)

        return withdrawal

    except Exception:
        db.rollback()
        raise


def get_withdrawals(
    db: Session,
    current_user: User,
):
    withdrawals = (
        db.query(Withdrawal)
        .filter(Withdrawal.user_id == current_user.id)
        .order_by(Withdrawal.created_at.desc())
        .all()
    )

    return {
        "total": len(withdrawals),
        "withdrawals": withdrawals,
    }


def process_pending_withdrawals(
    db: Session,
    batch_size: int = 50,
):
    """
    Process pending withdrawals.

    Simulation rule:
    - Account number ending in 0000: fail and reverse.
    - Other account numbers: complete the withdrawal.

    This function is intended to be called by APScheduler.
    """

    pending_ids = [
        row.id
        for row in (
            db.query(Withdrawal.id)
            .filter(Withdrawal.status == "Pending")
            .order_by(Withdrawal.created_at.asc())
            .limit(batch_size)
            .all()
        )
    ]

    completed_count = 0
    failed_count = 0

    for withdrawal_id in pending_ids:

        try:
            withdrawal = (
                db.query(Withdrawal)
                .filter(Withdrawal.id == withdrawal_id)
                .with_for_update()
                .first()
            )

            if not withdrawal or withdrawal.status != "Pending":
                db.rollback()
                continue

            bank_account = (
                db.query(BankAccount)
                .filter(
                    BankAccount.id == withdrawal.bank_account_id
                )
                .with_for_update()
                .first()
            )

            original_transaction = (
                db.query(FinancialTransaction)
                .filter(
                    FinancialTransaction.id
                    == withdrawal.transaction_id
                )
                .with_for_update()
                .first()
            )

            if not bank_account or not original_transaction:
                raise RuntimeError(
                    "Withdrawal bank account or transaction was not found."
                )

            amount = money(withdrawal.amount)

            if bank_account.account_number.endswith("0000"):

                # Build the opposite postings of the original transaction.
                original_entries = (
                    db.query(LedgerEntry)
                    .filter(
                        LedgerEntry.transaction_id
                        == original_transaction.id
                    )
                    .order_by(LedgerEntry.id)
                    .all()
                )

                if not original_entries:
                    raise RuntimeError(
                        "Original withdrawal has no ledger entries."
                    )

                reversal_postings = []

                for entry in original_entries:
                    opposite_type = (
                        "Credit"
                        if entry.entry_type == "Debit"
                        else "Debit"
                    )

                    reversal_postings.append(
                        (
                            entry.account_id,
                            opposite_type,
                            money(entry.amount),
                        )
                    )

                # Reverse the original transaction without committing yet.
                post_transaction(
                    db=db,
                    initiated_by=withdrawal.user_id,
                    transaction_type="Reversal",
                    amount=amount,
                    postings=reversal_postings,
                    description="Failed withdrawal reversal",
                    reversal_of_id=original_transaction.id,
                    commit=False,
                )

                withdrawal.status = "Failed"
                withdrawal.failure_reason = (
                    "Bank rejected the withdrawal. "
                    "The amount has been returned to your wallet."
                )

                withdrawal.processed_at = utc_now()

                db.commit()
                failed_count += 1

            else:

                clearing_account = get_system_account(
                    db=db,
                    system_code="WITHDRAWAL_CLEARING",
                )

                bank_settlement_account = get_system_account(
                    db=db,
                    system_code="BANK_SETTLEMENT",
                )

                # Move the amount from Withdrawal Clearing to Bank Settlement.
                post_transaction(
                    db=db,
                    initiated_by=withdrawal.user_id,
                    transaction_type="Withdrawal Settlement",
                    amount=amount,
                    postings=[
                        (
                            clearing_account.id,
                            "Debit",
                            amount,
                        ),
                        (
                            bank_settlement_account.id,
                            "Credit",
                            amount,
                        ),
                    ],
                    description="Withdrawal successfully processed",
                    commit=False,
                )

                withdrawal.status = "Completed"
                withdrawal.failure_reason = None
                withdrawal.processed_at = utc_now()

                db.commit()
                completed_count += 1

        except Exception:
            db.rollback()
            raise

    return {
        "processed": completed_count + failed_count,
        "completed": completed_count,
        "failed": failed_count,
    }
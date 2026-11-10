from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.wallet import Wallet
from app.models.ledger_account import LedgerAccount
from app.models.financial_transaction import FinancialTransaction
from app.models.fraud_review import FraudReview

from app.services.ledger_service import (
    money,
    get_system_account,
    get_or_create_wallet_account,
    post_transaction,
)


def utc_now():
    return datetime.now(timezone.utc)


def get_pending_review(
    db: Session,
    transaction_ref: str,
):
    review = (
        db.query(FraudReview)
        .join(
            FinancialTransaction,
            FinancialTransaction.id == FraudReview.transaction_id,
        )
        .filter(
            FinancialTransaction.transaction_ref == transaction_ref,
        )
        .with_for_update()
        .first()
    )

    if not review:
        raise HTTPException(
            status_code=404,
            detail="Fraud review not found.",
        )

    if review.status != "Pending":
        raise HTTPException(
            status_code=409,
            detail=f"This review has already been {review.status.lower()}.",
        )

    if review.transaction.status != "On Hold":
        raise HTTPException(
            status_code=409,
            detail="The original transaction is not On Hold.",
        )

    return review


def get_wallet_and_lock(
    db: Session,
    user_id: int,
):
    wallet = (
        db.query(Wallet)
        .filter(Wallet.owner_id == user_id)
        .with_for_update()
        .first()
    )

    if not wallet:
        raise HTTPException(
            status_code=404,
            detail=f"Wallet not found for user {user_id}.",
        )

    return wallet


def get_wallet_account(
    db: Session,
    user: User,
    wallet: Wallet,
):
    role = getattr(user.role, "value", user.role)

    account_type = (
        "Merchant Wallet"
        if role == "Merchant"
        else "User Wallet"
    )

    return get_or_create_wallet_account(
        db=db,
        wallet=wallet,
        account_type=account_type,
    )


def list_flagged_transactions(
    db: Session,
    status: str = "Pending",
    limit: int = 50,
    offset: int = 0,
):
    valid_statuses = ["Pending", "Approved", "Rejected", "All"]

    if status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail="Status must be Pending, Approved, Rejected, or All.",
        )

    query = (
        db.query(FraudReview)
        .join(
            FinancialTransaction,
            FinancialTransaction.id == FraudReview.transaction_id,
        )
    )

    if status != "All":
        query = query.filter(FraudReview.status == status)

    reviews = (
        query
        .order_by(FraudReview.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "total_returned": len(reviews),
        "reviews": [
            {
                "review_id": review.id,
                "transaction_ref": review.transaction.transaction_ref,
                "transaction_type": review.transaction.type,
                "amount": money(review.transaction.amount),
                "transaction_status": review.transaction.status,
                "review_status": review.status,
                "sender": {
                    "user_id": review.sender.id,
                    "name": review.sender.full_name,
                    "email": review.sender.email,
                    "phone": review.sender.phone,
                },
                "receiver": {
                    "user_id": review.receiver.id,
                    "name": review.receiver.full_name,
                    "email": review.receiver.email,
                    "phone": review.receiver.phone,
                },
                "flag_reason": review.flag_reason,
                "admin_id": review.admin_id,
                "decision_reason": review.decision_reason,
                "decided_at": review.decided_at,
                "created_at": review.created_at,
            }
            for review in reviews
        ],
    }


def approve_flagged_transaction(
    db: Session,
    admin: User,
    transaction_ref: str,
    decision_reason: str | None = None,
):
    try:
        review = get_pending_review(db, transaction_ref)

        original_transaction = review.transaction

        receiver = (
            db.query(User)
            .filter(User.id == review.receiver_user_id)
            .with_for_update()
            .first()
        )

        if not receiver or not receiver.is_active:
            raise HTTPException(
                status_code=409,
                detail="Receiver account is unavailable. Transfer remains On Hold.",
            )

        receiver_wallet = get_wallet_and_lock(
            db,
            receiver.id,
        )

        if receiver_wallet.status != "Active":
            raise HTTPException(
                status_code=409,
                detail="Receiver wallet is not active. Transfer remains On Hold.",
            )

        hold_account = get_system_account(
            db,
            "HOLD",
        )

        receiver_account = get_wallet_account(
            db,
            receiver,
            receiver_wallet,
        )

        release_transaction = post_transaction(
            db=db,
            initiated_by=admin.id,
            transaction_type="Fraud Approval",
            amount=money(original_transaction.amount),
            postings=[
                (
                    hold_account.id,
                    "Debit",
                    money(original_transaction.amount),
                ),
                (
                    receiver_account.id,
                    "Credit",
                    money(original_transaction.amount),
                ),
            ],
            description=(
                f"Admin approved held transfer "
                f"{original_transaction.transaction_ref}"
            ),
            related_transaction_id=original_transaction.id,
            commit=False,
        )

        original_transaction.status = "Success"

        review.status = "Approved"
        review.admin_id = admin.id
        review.decision_reason = (
            decision_reason.strip()
            if decision_reason and decision_reason.strip()
            else "Approved by Admin."
        )
        review.decided_at = utc_now()

        db.commit()
        db.refresh(release_transaction)
        db.refresh(review)

        return {
            "message": "Held transfer approved. Money released to receiver.",
            "original_transaction_ref": original_transaction.transaction_ref,
            "release_transaction_ref": release_transaction.transaction_ref,
            "amount": money(original_transaction.amount),
            "review_status": review.status,
            "admin_id": admin.id,
            "decided_at": review.decided_at,
        }

    except Exception:
        db.rollback()
        raise


def reject_flagged_transaction(
    db: Session,
    admin: User,
    transaction_ref: str,
    decision_reason: str,
):
    if not decision_reason or len(decision_reason.strip()) < 3:
        raise HTTPException(
            status_code=422,
            detail="A rejection reason of at least 3 characters is required.",
        )

    try:
        review = get_pending_review(db, transaction_ref)

        original_transaction = review.transaction

        sender = (
            db.query(User)
            .filter(User.id == review.sender_user_id)
            .with_for_update()
            .first()
        )

        if not sender:
            raise HTTPException(
                status_code=404,
                detail="Original sender account not found.",
            )

        # A frozen wallet can still receive returned funds.
        sender_wallet = get_wallet_and_lock(
            db,
            sender.id,
        )

        sender_account = get_wallet_account(
            db,
            sender,
            sender_wallet,
        )

        hold_account = get_system_account(
            db,
            "HOLD",
        )

        reversal_transaction = post_transaction(
            db=db,
            initiated_by=admin.id,
            transaction_type="Fraud Reversal",
            amount=money(original_transaction.amount),
            postings=[
                (
                    hold_account.id,
                    "Debit",
                    money(original_transaction.amount),
                ),
                (
                    sender_account.id,
                    "Credit",
                    money(original_transaction.amount),
                ),
            ],
            description=(
                f"Admin rejected held transfer "
                f"{original_transaction.transaction_ref}: "
                f"{decision_reason.strip()}"
            ),
            reversal_of_id=original_transaction.id,
            related_transaction_id=original_transaction.id,
            commit=False,
        )

        original_transaction.status = "Rejected"

        review.status = "Rejected"
        review.admin_id = admin.id
        review.decision_reason = decision_reason.strip()
        review.decided_at = utc_now()

        db.commit()
        db.refresh(reversal_transaction)
        db.refresh(review)

        return {
            "message": "Held transfer rejected. Money returned to sender.",
            "original_transaction_ref": original_transaction.transaction_ref,
            "reversal_transaction_ref": reversal_transaction.transaction_ref,
            "amount": money(original_transaction.amount),
            "review_status": review.status,
            "admin_id": admin.id,
            "decided_at": review.decided_at,
        }

    except Exception:
        db.rollback()
        raise
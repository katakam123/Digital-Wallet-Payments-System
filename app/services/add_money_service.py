
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.wallet import Wallet
from app.models.financial_transaction import FinancialTransaction

from app.services.ledger_service import (
    money,
    generate_transaction_ref,
    get_system_account,
    get_or_create_wallet_account,
    post_transaction,
)


MIN_ADD_AMOUNT = Decimal("10.00")
MAX_ADD_AMOUNT = Decimal("50000.00")

KYC_WALLET_LIMITS = {
    "Minimum": Decimal("10000.00"),
    "Full": Decimal("200000.00"),
}


def add_money(
    db: Session,
    current_user: User,
    amount: Decimal,
    source: str,
    simulate_status: str,
):
    # Validate amount precision and value.
    try:
        amount = money(amount)
    except (ValueError, TypeError, ArithmeticError):
        raise HTTPException(
            status_code=422,
            detail="Invalid amount. Use a maximum of two decimal places."
        )

    if amount < MIN_ADD_AMOUNT or amount > MAX_ADD_AMOUNT:
        raise HTTPException(
            status_code=400,
            detail="Add-money amount must be between ₹10 and ₹50,000."
        )

    if source not in ["UPI", "Card", "Net Banking"]:
        raise HTTPException(
            status_code=422,
            detail="Source must be UPI, Card, or Net Banking."
        )

    if simulate_status not in ["Success", "Failed"]:
        raise HTTPException(
            status_code=422,
            detail="simulate_status must be Success or Failed."
        )

    # Lock the wallet before checking or changing its balance.
    wallet = (
        db.query(Wallet)
        .filter(Wallet.owner_id == current_user.id)
        .with_for_update()
        .first()
    )

    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found.")

    if wallet.status != "Active":
        raise HTTPException(
            status_code=403,
            detail="Your wallet is not active."
        )

    # Save a failed attempt without ledger entries.
    if simulate_status == "Failed":
        failed_transaction = FinancialTransaction(
            transaction_ref=generate_transaction_ref(),
            type="Add Money",
            amount=amount,
            status="Failed",
            initiated_by=current_user.id,
            description=f"Add money via {source} - simulated payment failure",
            is_flagged=False,
        )

        try:
            db.add(failed_transaction)
            db.commit()
            db.refresh(failed_transaction)

            return {
                "transaction_ref": failed_transaction.transaction_ref,
                "transaction_type": "Add Money",
                "amount": amount,
                "source": source,
                "status": "Failed",
                "wallet_balance": wallet.balance,
                "message": "Payment failed. Wallet balance was not changed."
            }

        except Exception:
            db.rollback()
            raise

    # Check the user's KYC wallet balance limit.
    wallet_limit = KYC_WALLET_LIMITS.get(wallet.kyc_level)

    if wallet_limit is None:
        raise HTTPException(
            status_code=400,
            detail="Invalid wallet KYC level."
        )

    if wallet.balance + amount > wallet_limit:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Wallet balance limit exceeded. "
                f"Your {wallet.kyc_level} KYC wallet limit is "
                f"₹{wallet_limit}."
            )
        )

    # Get the user's wallet ledger account.
    account_type = (
        "Merchant Wallet"
        if current_user.role == "Merchant"
        else "User Wallet"
    )

    wallet_account = get_or_create_wallet_account(
        db,
        wallet,
        account_type
    )

    # Bank Settlement is debited; the wallet is credited.
    bank_account = get_system_account(
        db,
        "BANK_SETTLEMENT",
        lock=False
    )

    if not bank_account:
        raise HTTPException(
            status_code=500,
            detail="Bank Settlement ledger account not found."
        )

    try:
        transaction = post_transaction(
            db=db,
            initiated_by=current_user.id,
            transaction_type="Add Money",
            amount=amount,
            postings=[
                (bank_account, "Debit", amount),
                (wallet_account, "Credit", amount),
            ],
            description=f"Wallet top-up via {source}",
            is_flagged=False,
        )

        db.refresh(wallet)

        return {
            "transaction_ref": transaction.transaction_ref,
            "transaction_type": "Add Money",
            "amount": amount,
            "source": source,
            "status": transaction.status,
            "wallet_balance": wallet.balance,
            "message": "Money added to wallet successfully."
        }

    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Unable to process add-money transaction."
        )

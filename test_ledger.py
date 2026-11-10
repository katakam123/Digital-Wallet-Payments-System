from decimal import Decimal

from app.database import SessionLocal
from app.models.wallet import Wallet
from app.models.user import User
from app.services.ledger_service import (
    get_system_account,
    get_or_create_wallet_account,
    post_transaction,
)


db = SessionLocal()

try:
    user = db.query(User).first()

    if not user:
        print("Register a user first.")
        raise SystemExit

    wallet = (
        db.query(Wallet)
        .filter(Wallet.owner_id == user.id)
        .first()
    )

    if not wallet:
        print("Wallet not found.")
        raise SystemExit

    bank_account = get_system_account(
        db,
        "BANK_SETTLEMENT",
    )

    wallet_account = get_or_create_wallet_account(
        db,
        wallet,
        "User Wallet",
    )

    transaction = post_transaction(
        db=db,
        initiated_by=user.id,
        transaction_type="Add Money",
        amount=Decimal("1000.00"),
        postings=[
            (
                bank_account.id,
                "Debit",
                Decimal("1000.00"),
            ),
            (
                wallet_account.id,
                "Credit",
                Decimal("1000.00"),
            ),
        ],
        description="Test wallet deposit",
    )

    print("Transaction successful!")
    print("Reference:", transaction.transaction_ref)
    print("Status:", transaction.status)

    db.refresh(wallet)

    print("Updated wallet balance:", wallet.balance)

finally:
    db.close()
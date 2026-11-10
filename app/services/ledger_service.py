
import secrets
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.ledger_account import LedgerAccount
from app.models.ledger_entry import LedgerEntry
from app.models.financial_transaction import FinancialTransaction
from app.models.wallet import Wallet


# ==================================================
# CONSTANTS
# ==================================================

MONEY = Decimal("0.01")
ZERO = Decimal("0.00")

ACCOUNT_NORMAL_BALANCE = {
    "User Wallet": "Credit",
    "Merchant Wallet": "Credit",
    "Bank Settlement": "Debit",
    "Cashback Pool": "Debit",
    "Fees": "Credit",
    "Withdrawal Clearing": "Debit",
    "Hold": "Credit",
}

SYSTEM_ACCOUNTS = [
    ("BANK_SETTLEMENT", "Bank Settlement", "Debit"),
    ("CASHBACK_POOL", "Cashback Pool", "Debit"),
    ("FEES", "Fees", "Credit"),
    ("WITHDRAWAL_CLEARING", "Withdrawal Clearing", "Debit"),
    ("HOLD", "Hold", "Credit"),
]


# ==================================================
# MONEY HELPER
# ==================================================

def money(value) -> Decimal:
    """
    Convert a value to Decimal.

    - Reject float input.
    - Reject NaN and infinity.
    - Reject more than two decimal places.
    - Do not silently round financial input.
    """

    try:
        if isinstance(value, float):
            raise ValueError("Float values are not accepted.")

        result = Decimal(str(value))

        if not result.is_finite():
            raise ValueError("Amount must be finite.")

        if result != result.quantize(MONEY):
            raise ValueError(
                "Amount cannot contain more than two decimal places."
            )

        return result.quantize(MONEY)

    except (
        InvalidOperation,
        ValueError,
        TypeError,
        ArithmeticError,
    ):
        raise ValueError("Invalid money amount.")


# ==================================================
# TRANSACTION REFERENCE
# ==================================================

def generate_transaction_ref() -> str:
    """
    Generate a transaction reference.

    Example:
    TXN-20261110-A1B2C3
    """

    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    random_part = secrets.token_hex(3).upper()

    return f"TXN-{date_part}-{random_part}"


# ==================================================
# CREATE SYSTEM ACCOUNTS
# ==================================================

def create_system_accounts(db: Session):
    """
    Create required system ledger accounts if missing.

    Run after Alembic migrations.
    """

    try:
        for system_code, account_type, normal_balance in SYSTEM_ACCOUNTS:

            account = (
                db.query(LedgerAccount)
                .filter(
                    LedgerAccount.system_code == system_code
                )
                .first()
            )

            if account:

                if (
                    account.account_type != account_type
                    or account.normal_balance != normal_balance
                ):
                    raise RuntimeError(
                        f"Incorrect configuration for system account "
                        f"{system_code}."
                    )

                continue

            new_account = LedgerAccount(
                system_code=system_code,
                account_type=account_type,
                wallet_id=None,
                normal_balance=normal_balance,
                current_balance=ZERO,
            )

            db.add(new_account)

        db.commit()

    except Exception:
        db.rollback()
        raise


# ==================================================
# GET SYSTEM ACCOUNT
# ==================================================

def get_system_account(
    db: Session,
    system_code: str,
    lock: bool = False,
) -> LedgerAccount:
    """
    Retrieve a system ledger account.

    Normally use lock=False when preparing postings.
    post_transaction() performs account locking itself.
    """

    query = (
        db.query(LedgerAccount)
        .filter(
            LedgerAccount.system_code == system_code
        )
    )

    if lock:
        query = query.with_for_update()

    account = query.first()

    if not account:
        raise HTTPException(
            status_code=500,
            detail=f"System account {system_code} does not exist.",
        )

    return account


# ==================================================
# GET OR CREATE WALLET LEDGER ACCOUNT
# ==================================================

def get_or_create_wallet_account(
    db: Session,
    wallet: Wallet,
    account_type: str = "User Wallet",
) -> LedgerAccount:
    """
    Each wallet must have exactly one ledger account.

    New ledger accounts can only be created for zero-balance wallets.
    """

    if account_type not in (
        "User Wallet",
        "Merchant Wallet",
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid wallet account type.",
        )

    account = (
        db.query(LedgerAccount)
        .filter(
            LedgerAccount.wallet_id == wallet.id
        )
        .with_for_update()
        .first()
    )

    if account:

        if account.normal_balance != "Credit":
            raise HTTPException(
                status_code=500,
                detail="Wallet ledger account must use Credit normal balance.",
            )

        if account.account_type != account_type:
            raise HTTPException(
                status_code=409,
                detail="Wallet ledger account type does not match wallet owner.",
            )

        return account

    wallet_balance = money(wallet.balance)

    if wallet_balance != ZERO:
        raise HTTPException(
            status_code=409,
            detail=(
                "Cannot create a ledger account for a nonzero wallet "
                "without an opening-balance transaction."
            ),
        )

    account = LedgerAccount(
        account_type=account_type,
        wallet_id=wallet.id,
        system_code=None,
        normal_balance="Credit",
        current_balance=ZERO,
    )

    db.add(account)
    db.flush()

    return account


# ==================================================
# POST FINANCIAL TRANSACTION
# ==================================================

def post_transaction(
    db: Session,
    initiated_by: int,
    transaction_type: str,
    amount: Decimal,
    postings: list[tuple[int, str, Decimal]],
    description: str | None = None,
    is_flagged: bool = False,
    reversal_of_id: int | None = None,
    related_transaction_id: int | None = None,
    commit: bool = True,
) -> FinancialTransaction:
    """
    Post a balanced double-entry financial transaction.

    Example:

    postings = [
        (bank_account.id, "Debit", Decimal("1000.00")),
        (wallet_account.id, "Credit", Decimal("1000.00")),
    ]

    Important rules:

    1. Total debit must equal total credit.
    2. Transaction amount must match posting totals.
    3. Wallet rows are locked in ascending ID order.
    4. Ledger accounts are locked in ascending ID order.
    5. Wallet balance and ledger balance update together.
    6. Wallet ledger balances cannot become negative.
    7. Ledger entries are never edited or deleted.
    8. commit=False leaves the outer transaction to the caller.
    9. related_transaction_id links partial refunds to original payments.
    """

    try:

        # ------------------------------------------
        # 1. Validate transaction amount
        # ------------------------------------------

        amount = money(amount)

        if amount <= ZERO:
            raise HTTPException(
                status_code=400,
                detail="Transaction amount must be greater than zero.",
            )

        if not postings:
            raise HTTPException(
                status_code=400,
                detail="Ledger postings are required.",
            )

        if reversal_of_id is not None and transaction_type != "Reversal":
            raise HTTPException(
                status_code=400,
                detail="A reversal reference requires transaction type Reversal.",
            )

        if transaction_type == "Reversal" and reversal_of_id is None:
            raise HTTPException(
                status_code=400,
                detail="Reversal must reference an original transaction.",
            )

        if reversal_of_id is not None and related_transaction_id is not None:
            raise HTTPException(
                status_code=400,
                detail="A transaction cannot be both a reversal and a related refund.",
            )

        # ------------------------------------------
        # 2. Validate ledger postings
        # ------------------------------------------

        normalized = []

        for account_id, entry_type, entry_amount in postings:

            entry_amount = money(entry_amount)

            if entry_type not in ("Debit", "Credit"):
                raise HTTPException(
                    status_code=400,
                    detail="Entry type must be Debit or Credit.",
                )

            if entry_amount <= ZERO:
                raise HTTPException(
                    status_code=400,
                    detail="Ledger entry amount must be positive.",
                )

            normalized.append(
                (
                    int(account_id),
                    entry_type,
                    entry_amount,
                )
            )

        total_debits = sum(
            (
                value
                for _, entry_type, value in normalized
                if entry_type == "Debit"
            ),
            ZERO,
        )

        total_credits = sum(
            (
                value
                for _, entry_type, value in normalized
                if entry_type == "Credit"
            ),
            ZERO,
        )

        if total_debits == ZERO or total_credits == ZERO:
            raise HTTPException(
                status_code=400,
                detail="A transaction must contain both debit and credit entries.",
            )

        if total_debits != total_credits:
            raise HTTPException(
                status_code=400,
                detail="Ledger is unbalanced. Debits must equal credits.",
            )

        if total_debits != amount:
            raise HTTPException(
                status_code=400,
                detail="Ledger total must equal the transaction amount.",
            )

        # ------------------------------------------
        # 3. Validate full reversal
        # ------------------------------------------

        original = None

        if reversal_of_id is not None:

            original = (
                db.query(FinancialTransaction)
                .filter(
                    FinancialTransaction.id == reversal_of_id
                )
                .with_for_update()
                .first()
            )

            if not original:
                raise HTTPException(
                    status_code=404,
                    detail="Original transaction not found.",
                )

            if original.status != "Success":
                raise HTTPException(
                    status_code=409,
                    detail="Only successful transactions can be reversed.",
                )

            if money(original.amount) != amount:
                raise HTTPException(
                    status_code=400,
                    detail="Reversal amount must match the original transaction.",
                )

            existing_reversal = (
                db.query(FinancialTransaction)
                .filter(
                    FinancialTransaction.reversal_of_id == original.id,
                    FinancialTransaction.type == "Reversal",
                )
                .first()
            )

            if existing_reversal:
                raise HTTPException(
                    status_code=409,
                    detail="This transaction has already been reversed.",
                )

        # ------------------------------------------
        # 4. Validate related transaction reference
        # ------------------------------------------

        if related_transaction_id is not None:

            related_transaction = (
                db.query(FinancialTransaction)
                .filter(
                    FinancialTransaction.id == related_transaction_id
                )
                .first()
            )

            if not related_transaction:
                raise HTTPException(
                    status_code=404,
                    detail="Related transaction not found.",
                )

        # ------------------------------------------
        # 5. Collect account IDs
        # ------------------------------------------

        account_ids = sorted(
            set(
                account_id
                for account_id, _, _ in normalized
            )
        )

        # ------------------------------------------
        # 6. Find affected wallet IDs
        # ------------------------------------------

        account_wallet_rows = (
            db.query(
                LedgerAccount.id,
                LedgerAccount.wallet_id,
            )
            .filter(
                LedgerAccount.id.in_(account_ids)
            )
            .all()
        )

        if len(account_wallet_rows) != len(account_ids):
            raise HTTPException(
                status_code=404,
                detail="One or more ledger accounts do not exist.",
            )

        wallet_ids = sorted({
            wallet_id
            for _, wallet_id in account_wallet_rows
            if wallet_id is not None
        })

        # ------------------------------------------
        # 7. Lock wallet rows FIRST
        # ------------------------------------------

        wallets = (
            db.query(Wallet)
            .filter(
                Wallet.id.in_(wallet_ids)
            )
            .order_by(Wallet.id)
            .with_for_update()
            .all()
        ) if wallet_ids else []

        wallet_map = {
            wallet.id: wallet
            for wallet in wallets
        }

        if len(wallet_map) != len(wallet_ids):
            raise HTTPException(
                status_code=404,
                detail="One or more wallets do not exist.",
            )

        # ------------------------------------------
        # 8. Lock ledger accounts SECOND
        # ------------------------------------------

        accounts = (
            db.query(LedgerAccount)
            .filter(
                LedgerAccount.id.in_(account_ids)
            )
            .order_by(LedgerAccount.id)
            .with_for_update()
            .all()
        )

        account_map = {
            account.id: account
            for account in accounts
        }

        if len(account_map) != len(account_ids):
            raise HTTPException(
                status_code=404,
                detail="One or more ledger accounts do not exist.",
            )

        # ------------------------------------------
        # 9. Create financial transaction
        # ------------------------------------------

        transaction = FinancialTransaction(
            transaction_ref=generate_transaction_ref(),
            type=transaction_type,
            amount=amount,
            status="Pending",
            initiated_by=initiated_by,
            description=description,
            is_flagged=is_flagged,
            reversal_of_id=reversal_of_id,
            related_transaction_id=related_transaction_id,
        )

        db.add(transaction)
        db.flush()

        # ------------------------------------------
        # 10. Combine duplicate postings
        # ------------------------------------------

        combined = {}

        for account_id, entry_type, value in normalized:

            key = (account_id, entry_type)

            combined[key] = (
                combined.get(key, ZERO) + value
            )

        # ------------------------------------------
        # 11. Update ledger balances and entries
        # ------------------------------------------

        for (account_id, entry_type), value in sorted(combined.items()):

            account = account_map[account_id]

            if account.normal_balance not in ("Debit", "Credit"):
                raise HTTPException(
                    status_code=500,
                    detail="Invalid ledger account normal balance.",
                )

            if entry_type == account.normal_balance:
                account.current_balance += value
            else:
                account.current_balance -= value

            account.current_balance = money(
                account.current_balance
            )

            # Wallet ledger accounts cannot have negative balances.
            # System ledger accounts follow their normal balance rules.
            if (
                account.wallet_id is not None
                and account.current_balance < ZERO
            ):
                raise HTTPException(
                    status_code=409,
                    detail="Insufficient wallet ledger balance.",
                )

            db.add(
                LedgerEntry(
                    transaction_id=transaction.id,
                    account_id=account.id,
                    entry_type=entry_type,
                    amount=value,
                    balance_after=account.current_balance,
                )
            )

        # ------------------------------------------
        # 12. Synchronize wallet balances
        # ------------------------------------------

        for account in accounts:

            if account.wallet_id is None:
                continue

            if account.normal_balance != "Credit":
                raise HTTPException(
                    status_code=500,
                    detail="Wallet account must have Credit normal balance.",
                )

            wallet = wallet_map.get(account.wallet_id)

            if not wallet:
                raise HTTPException(
                    status_code=404,
                    detail="Wallet for ledger account was not found.",
                )

            wallet.balance = money(account.current_balance)

        # ------------------------------------------
        # 13. Mark original full reversal
        # ------------------------------------------

        if original is not None:
            original.status = "Reversed"

        # ------------------------------------------
        # 14. Complete transaction
        # ------------------------------------------

        transaction.status = "Success"

        if commit:
            db.commit()
            db.refresh(transaction)
        else:
            db.flush()

        return transaction

    except Exception:
        db.rollback()
        raise


# ==================================================
# REVERSE TRANSACTION
# ==================================================

def reverse_transaction(
    db: Session,
    original_transaction_id: int,
    initiated_by: int,
    description: str = "Transaction reversal",
) -> FinancialTransaction:
    """
    Reverse a complete successful transaction.

    Original ledger entries remain unchanged.
    Opposite ledger entries are created.

    Do not use this function for partial refunds.
    Use Merchant Refund transactions with related_transaction_id.
    """

    try:

        original = (
            db.query(FinancialTransaction)
            .filter(
                FinancialTransaction.id == original_transaction_id
            )
            .with_for_update()
            .first()
        )

        if not original:
            raise HTTPException(
                status_code=404,
                detail="Original transaction not found.",
            )

        if original.status != "Success":
            raise HTTPException(
                status_code=400,
                detail="Only successful transactions can be reversed.",
            )

        original_entries = (
            db.query(LedgerEntry)
            .filter(
                LedgerEntry.transaction_id == original.id
            )
            .order_by(LedgerEntry.id)
            .all()
        )

        if not original_entries:
            raise HTTPException(
                status_code=400,
                detail="Original transaction has no ledger entries.",
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

        reversal = post_transaction(
            db=db,
            initiated_by=initiated_by,
            transaction_type="Reversal",
            amount=money(original.amount),
            postings=reversal_postings,
            description=description,
            is_flagged=False,
            reversal_of_id=original.id,
            commit=True,
        )

        return reversal

    except Exception:
        db.rollback()
        raise

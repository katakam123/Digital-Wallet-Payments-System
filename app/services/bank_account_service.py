from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.bank_account import BankAccount
from app.schemas.bank_account import BankAccountCreate
from app.services.pin_otp_service import (
    verify_otp,
    consume_otp_authorization,
)


OTP_PURPOSE = "Add Bank Account"
MAX_BANK_ACCOUNTS = 3


def mask_account_number(account_number: str) -> str:
    """Show only the last four digits."""
    return ("X" * (len(account_number) - 4)) + account_number[-4:]


def bank_account_to_dict(bank: BankAccount) -> dict:
    """Return bank details without exposing the full account number."""
    return {
        "id": bank.id,
        "account_holder_name": bank.account_holder_name,
        "masked_account_number": mask_account_number(
            bank.account_number
        ),
        "ifsc_code": bank.ifsc_code,
        "bank_name": bank.bank_name,
        "is_primary": bank.is_primary,
        "created_at": bank.created_at,
    }


def add_bank_account(
    db: Session,
    current_user: User,
    request: BankAccountCreate,
):
    # Lock the user's row before checking the account limit.
    locked_user = (
        db.query(User)
        .filter(User.id == current_user.id)
        .with_for_update()
        .first()
    )

    if not locked_user or not locked_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is not active.",
        )

    existing_count = (
        db.query(BankAccount)
        .filter(BankAccount.user_id == locked_user.id)
        .count()
    )

    if existing_count >= MAX_BANK_ACCOUNTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You can add a maximum of 3 bank accounts.",
        )

    duplicate = (
        db.query(BankAccount)
        .filter(
            BankAccount.user_id == locked_user.id,
            BankAccount.account_number == request.account_number,
        )
        .first()
    )

    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This bank account is already added.",
        )

    # Verify the OTP using your existing OTP service.
    verify_otp(
        db=db,
        user=locked_user,
        purpose=OTP_PURPOSE,
        otp_value=request.otp,
    )

    # verify_otp() commits, so reacquire the user row lock.
    locked_user = (
        db.query(User)
        .filter(User.id == current_user.id)
        .with_for_update()
        .first()
    )

    # Check the account limit and duplicate again after the OTP commit.
    existing_count = (
        db.query(BankAccount)
        .filter(BankAccount.user_id == locked_user.id)
        .count()
    )

    if existing_count >= MAX_BANK_ACCOUNTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You can add a maximum of 3 bank accounts.",
        )

    duplicate = (
        db.query(BankAccount)
        .filter(
            BankAccount.user_id == locked_user.id,
            BankAccount.account_number == request.account_number,
        )
        .first()
    )

    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This bank account is already added.",
        )

    # Consume the temporary OTP authorization.
    consume_otp_authorization(
        user=locked_user,
        purpose=OTP_PURPOSE,
    )

    # The first bank account is automatically primary.
    make_primary = request.is_primary or existing_count == 0

    if make_primary:
        db.query(BankAccount).filter(
            BankAccount.user_id == locked_user.id
        ).update(
            {BankAccount.is_primary: False},
            synchronize_session=False,
        )

    bank = BankAccount(
        user_id=locked_user.id,
        account_holder_name=request.account_holder_name.strip(),
        account_number=request.account_number,
        ifsc_code=request.ifsc_code.upper(),
        bank_name=request.bank_name.strip(),
        is_primary=make_primary,
    )

    try:
        db.add(bank)
        db.commit()
        db.refresh(bank)
    except Exception:
        db.rollback()
        raise

    return bank_account_to_dict(bank)


def get_bank_accounts(
    db: Session,
    current_user: User,
):
    banks = (
        db.query(BankAccount)
        .filter(BankAccount.user_id == current_user.id)
        .order_by(
            BankAccount.is_primary.desc(),
            BankAccount.created_at.desc(),
        )
        .all()
    )

    return {
        "total": len(banks),
        "bank_accounts": [
            bank_account_to_dict(bank) for bank in banks
        ],
    }


def delete_bank_account(
    db: Session,
    current_user: User,
    bank_account_id: int,
):
    bank = (
        db.query(BankAccount)
        .filter(
            BankAccount.id == bank_account_id,
            BankAccount.user_id == current_user.id,
        )
        .with_for_update()
        .first()
    )

    if not bank:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bank account not found.",
        )

    was_primary = bank.is_primary

    try:
        db.delete(bank)
        db.flush()

        # If the deleted account was primary, select another one.
        if was_primary:
            replacement = (
                db.query(BankAccount)
                .filter(
                    BankAccount.user_id == current_user.id
                )
                .order_by(BankAccount.created_at.asc())
                .first()
            )

            if replacement:
                replacement.is_primary = True

        db.commit()

    except Exception:
        db.rollback()
        raise

    return {
        "message": "Bank account deleted successfully."
    }
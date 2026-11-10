import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.models import user
from app.models.otp import OTP
from app.models.user import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

OTP_EXPIRY_MINUTES = 5
OTP_RESEND_SECONDS = 60
MAX_OTP_ATTEMPTS = 3
MAX_PIN_ATTEMPTS = 3
PIN_LOCK_MINUTES = 30


def utc_now():
    return datetime.now(timezone.utc)


def hash_secret(value: str) -> str:
    return pwd_context.hash(value)


def verify_secret(value: str, hashed_value: str) -> bool:
    return pwd_context.verify(value, hashed_value)


def set_transaction_pin(db: Session, user: User, pin: str):
    if user.transaction_pin_hash:
        raise HTTPException(
            status_code=409,
            detail="Transaction PIN is already set. Use the change PIN API.",
        )

    user.transaction_pin_hash = hash_secret(pin)
    user.pin_failed_attempts = 0
    user.pin_locked_until = None

    db.commit()

    return {"message": "Transaction PIN set successfully."}


def check_pin_lock(user: User):
    now = utc_now()
    locked_until = user.pin_locked_until

    if locked_until:
        # MySQL may return a naive datetime for a timezone-aware column.
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)

        if now < locked_until:
            remaining = int((locked_until - now).total_seconds())

            raise HTTPException(
                status_code=423,
                detail={
                    "message": "Payments are temporarily locked.",
                    "retry_after_seconds": remaining,
                },
            )

        # Lock period has expired.
        user.pin_locked_until = None
        user.pin_failed_attempts = 0


def verify_transaction_pin(
    db: Session,
    user: User,
    pin: str,
):
    check_pin_lock(user)

    if not user.transaction_pin_hash:
        raise HTTPException(
            status_code=400,
            detail="Please set your transaction PIN first.",
        )

    if not verify_secret(pin, user.transaction_pin_hash):
        user.pin_failed_attempts += 1

        if user.pin_failed_attempts >= MAX_PIN_ATTEMPTS:
            user.pin_locked_until = (
                utc_now() + timedelta(minutes=PIN_LOCK_MINUTES)
            )

        db.commit()

        if user.pin_locked_until:
            raise HTTPException(
                status_code=423,
                detail="Three incorrect PIN attempts. Payments locked for 30 minutes.",
            )

        raise HTTPException(
            status_code=400,
            detail=f"Incorrect PIN. Attempts remaining: "
                   f"{MAX_PIN_ATTEMPTS - user.pin_failed_attempts}",
        )

    user.pin_failed_attempts = 0
    user.pin_locked_until = None
    db.commit()

    return True


def change_transaction_pin(
    db: Session,
    user: User,
    old_pin: str,
    new_pin: str,
):
    check_pin_lock(user)

    if not user.transaction_pin_hash:
        raise HTTPException(
            status_code=400,
            detail="Please set your transaction PIN first.",
        )

    if not verify_secret(old_pin, user.transaction_pin_hash):
        user.pin_failed_attempts += 1

        if user.pin_failed_attempts >= MAX_PIN_ATTEMPTS:
            user.pin_locked_until = (
                utc_now() + timedelta(minutes=PIN_LOCK_MINUTES)
            )

        db.commit()

        if user.pin_locked_until:
            raise HTTPException(
                status_code=423,
                detail="Payments locked for 30 minutes due to incorrect PIN attempts.",
            )

        raise HTTPException(
            status_code=400,
            detail="Incorrect current PIN.",
        )

    if old_pin == new_pin:
        raise HTTPException(
            status_code=400,
            detail="New PIN must be different from the current PIN.",
        )

    user.transaction_pin_hash = hash_secret(new_pin)
    user.pin_failed_attempts = 0
    user.pin_locked_until = None

    db.commit()

    return {"message": "Transaction PIN changed successfully."}


def generate_otp():
    return f"{secrets.randbelow(1_000_000):06d}"


def create_otp(db: Session, user: User, purpose: str):
    now = utc_now()

    previous_otp = (
        db.query(OTP)
        .filter(
            OTP.user_id == user.id,
            OTP.purpose == purpose,
        )
        .order_by(OTP.id.desc())
        .with_for_update()
        .first()
    )

    if previous_otp:
        created_at = previous_otp.created_at

        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        elapsed = (now - created_at).total_seconds()

        if elapsed < OTP_RESEND_SECONDS:
            wait_seconds = int(OTP_RESEND_SECONDS - elapsed) + 1

            raise HTTPException(
                status_code=429,
                detail=f"Please wait {wait_seconds} seconds before requesting another OTP.",
            )

    otp_value = generate_otp()

    otp_record = OTP(
        user_id=user.id,
        purpose=purpose,
        otp_hash=hash_secret(otp_value),
        expires_at=now + timedelta(minutes=OTP_EXPIRY_MINUTES),
        attempts=0,
        is_used=False,
    )

    db.add(otp_record)
    db.commit()
    db.refresh(otp_record)

    return otp_value


def verify_otp(
    db: Session,
    user: User,
    purpose: str,
    otp_value: str,
):
    now = utc_now()

    otp_record = (
        db.query(OTP)
        .filter(
            OTP.user_id == user.id,
            OTP.purpose == purpose,
            OTP.is_used.is_(False),
        )
        .order_by(OTP.id.desc())
        .with_for_update()
        .first()
    )

    if not otp_record:
        raise HTTPException(
            status_code=400,
            detail="No active OTP found. Request a new OTP.",
        )

    expires_at = otp_record.expires_at

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if now >= expires_at:
        otp_record.is_used = True
        db.commit()

        raise HTTPException(
            status_code=400,
            detail="OTP has expired. Request a new OTP.",
        )

    if otp_record.attempts >= MAX_OTP_ATTEMPTS:
        otp_record.is_used = True
        db.commit()

        raise HTTPException(
            status_code=429,
            detail="Maximum OTP attempts exceeded. Request a new OTP.",
        )

    if not verify_secret(otp_value, otp_record.otp_hash):
        otp_record.attempts += 1

        if otp_record.attempts >= MAX_OTP_ATTEMPTS:
            otp_record.is_used = True

        db.commit()

        raise HTTPException(
            status_code=400,
            detail="Incorrect OTP.",
        )

    # OTP is consumed only after a successful verification.
    otp_record.is_used = True

    verified_until = now + timedelta(minutes=5)

    if purpose == "PIN Reset":
        user.pin_reset_verified_until = verified_until

    elif purpose == "High Value Transfer":
        user.high_value_transfer_verified_until = verified_until

    elif purpose == "Add Bank Account":
        user.add_bank_verified_until = verified_until

    db.commit()

    return {"message": "OTP verified successfully."}
def consume_otp_authorization(user: User, purpose: str):
    now = utc_now()

    if purpose == "High Value Transfer":
        verified_until = user.high_value_transfer_verified_until

        if not verified_until:
            raise HTTPException(
                status_code=403,
                detail="OTP verification is required for this transfer.",
            )

        if verified_until.tzinfo is None:
            verified_until = verified_until.replace(tzinfo=timezone.utc)

        if now >= verified_until:
            user.high_value_transfer_verified_until = None
            raise HTTPException(
                status_code=403,
                detail="Transfer OTP verification has expired.",
            )

        user.high_value_transfer_verified_until = None

    elif purpose == "Add Bank Account":
        verified_until = user.add_bank_verified_until

        if not verified_until:
            raise HTTPException(
                status_code=403,
                detail="OTP verification is required to add a bank account.",
            )

        if verified_until.tzinfo is None:
            verified_until = verified_until.replace(tzinfo=timezone.utc)

        if now >= verified_until:
            user.add_bank_verified_until = None
            raise HTTPException(
                status_code=403,
                detail="Bank account OTP verification has expired.",
            )

        user.add_bank_verified_until = None

    else:
        raise HTTPException(
            status_code=400,
            detail="Unsupported OTP authorization purpose.",
        )

def verify_transaction_pin_for_payment(
    db: Session,
    user: User,
    pin: str,
):
    """
    Verify PIN specifically for money-moving operations.

    Successful verification:
        Does not commit. The payment service commits everything
        together with the financial transaction.

    Failed verification:
        Commits the failed-attempt counter so it is not lost
        when the payment request is rejected.

    The caller must lock the User row using SELECT FOR UPDATE
    before calling this function.
    """

    check_pin_lock(user)

    if not user.transaction_pin_hash:
        raise HTTPException(
            status_code=400,
            detail="Please set your transaction PIN first.",
        )

    if not verify_secret(pin, user.transaction_pin_hash):

        user.pin_failed_attempts += 1

        if user.pin_failed_attempts >= MAX_PIN_ATTEMPTS:
            user.pin_locked_until = (
                utc_now() + timedelta(minutes=PIN_LOCK_MINUTES)
            )

        # Persist failed attempts even though the payment fails.
        db.commit()

        if user.pin_locked_until:
            raise HTTPException(
                status_code=423,
                detail=(
                    "Three incorrect PIN attempts. "
                    "Payments locked for 30 minutes."
                ),
            )

        raise HTTPException(
            status_code=400,
            detail=(
                "Incorrect PIN. Attempts remaining: "
                f"{MAX_PIN_ATTEMPTS - user.pin_failed_attempts}"
            ),
        )

    # Successful verification.
    # Do not commit here.
    user.pin_failed_attempts = 0
    user.pin_locked_until = None

    return True

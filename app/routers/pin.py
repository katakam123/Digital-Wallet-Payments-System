from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.auth.security import get_current_user
from app.schemas.pin_otp import (
    SetPINSchema,
    ChangePINSchema,
    ResetPINSchema,
)
from app.services.pin_otp_service import (
    set_transaction_pin,
    change_transaction_pin,
    check_pin_lock,
    hash_secret,
    utc_now,
)

router = APIRouter(tags=["Transaction PIN"])


def get_locked_user(db: Session, user_id: int):
    user = (
        db.query(User)
        .filter(User.id == user_id)
        .with_for_update()
        .first()
    )

    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    return user


@router.post("/wallet/pin")
def set_pin(
    data: SetPINSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user = get_locked_user(db, current_user.id)

    result = set_transaction_pin(db, user, data.pin)

    return result


@router.put("/wallet/pin/change")
def change_pin(
    data: ChangePINSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user = get_locked_user(db, current_user.id)

    result = change_transaction_pin(
        db=db,
        user=user,
        old_pin=data.old_pin,
        new_pin=data.new_pin,
    )

    return result


@router.post("/wallet/pin/reset")
def reset_pin(
    data: ResetPINSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user = get_locked_user(db, current_user.id)

    verified_until = user.pin_reset_verified_until

    if not verified_until:
        raise HTTPException(
            status_code=403,
            detail="Verify a PIN Reset OTP before resetting your PIN.",
        )

    if verified_until.tzinfo is None:
        from datetime import timezone
        verified_until = verified_until.replace(tzinfo=timezone.utc)

    if utc_now() >= verified_until:
        user.pin_reset_verified_until = None
        db.commit()

        raise HTTPException(
            status_code=403,
            detail="PIN reset verification expired. Request and verify a new OTP.",
        )

    if user.transaction_pin_hash:
        from app.services.pin_otp_service import verify_secret

        # Prevent resetting to the same PIN.
        if verify_secret(data.new_pin, user.transaction_pin_hash):
            raise HTTPException(
                status_code=400,
                detail="New PIN must be different from your current PIN.",
            )

    user.transaction_pin_hash = hash_secret(data.new_pin)
    user.pin_failed_attempts = 0
    user.pin_locked_until = None
    user.pin_reset_verified_until = None

    db.commit()

    return {"message": "Transaction PIN reset successfully."}
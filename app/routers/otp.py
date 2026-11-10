from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.auth.security import get_current_user
from app.schemas.pin_otp import OTPSendSchema, OTPVerifySchema
from app.services.pin_otp_service import create_otp, verify_otp
from app.services.email_service import send_otp_email

router = APIRouter(tags=["OTP Verification"])


@router.post("/otp/send")
def send_otp(
    data: OTPSendSchema,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if data.purpose == "PIN Reset" and not current_user.transaction_pin_hash:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=400,
            detail="You have not set a transaction PIN yet.",
        )

    otp_value = create_otp(
        db=db,
        user=current_user,
        purpose=data.purpose,
    )

    background_tasks.add_task(
        send_otp_email,
        current_user.email,
        otp_value,
        data.purpose,
    )

    return {
        "message": "OTP request accepted. Check your registered email address.",
        "purpose": data.purpose,
        "expires_in_seconds": 300,
    }


@router.post("/otp/verify")
def verify_otp_api(
    data: OTPVerifySchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return verify_otp(
        db=db,
        user=current_user,
        purpose=data.purpose,
        otp_value=data.otp,
    )
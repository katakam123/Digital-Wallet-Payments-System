
from fastapi import APIRouter, Depends, HTTPException, status

from sqlalchemy.orm import Session

from app.database import get_db

from app.models.kyc import KYC
from app.models.user import User

from app.schemas.kyc import (
    KYCSubmitSchema,
    KYCResponse
)

from app.auth.security import (
    require_user_or_merchant
)


router = APIRouter(
    prefix="/kyc",
    tags=["KYC Verification"]
)


def safe_kyc_response(kyc: KYC):

    return {
        "id": kyc.id,
        "user_id": kyc.user_id,
        "pan_number": (
            "*****" + kyc.pan_number[-5:]
            if kyc.pan_number else ""
        ),
        "aadhaar_last4": kyc.aadhaar_last4,
        "full_name": kyc.full_name,
        "date_of_birth": kyc.date_of_birth,
        "status": kyc.status,
        "rejection_reason": kyc.rejection_reason
    }


# --------------------------------
# SUBMIT KYC
# --------------------------------

@router.post(
    "",
    response_model=KYCResponse,
    status_code=status.HTTP_201_CREATED
)
def submit_kyc(
    data: KYCSubmitSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_or_merchant)
):

    if current_user.kyc_status == "Approved":

        raise HTTPException(
            status_code=400,
            detail="Your KYC is already approved"
        )

    existing_pending = db.query(KYC).filter(
        KYC.user_id == current_user.id,
        KYC.status == "Pending"
    ).first()

    if existing_pending:

        raise HTTPException(
            status_code=409,
            detail="You already have a pending KYC application"
        )

    # Prevent PAN reuse by a different account
    existing_pan = db.query(KYC).filter(
        KYC.pan_number == data.pan_number
    ).first()

    if existing_pan:

        raise HTTPException(
            status_code=409,
            detail="This PAN is already associated with another application"
        )

    kyc = KYC(
        user_id=current_user.id,
        pan_number=data.pan_number,
        aadhaar_last4=data.aadhaar_last4,
        full_name=data.full_name,
        date_of_birth=data.date_of_birth,
        status="Pending"
    )

    try:

        db.add(kyc)

        current_user.kyc_status = "Pending"

        db.commit()
        db.refresh(kyc)

        return safe_kyc_response(kyc)

    except Exception:

        db.rollback()
        raise


# --------------------------------
# GET MY KYC
# --------------------------------

@router.get(
    "",
    response_model=KYCResponse
)
def get_my_kyc(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_or_merchant)
):

    kyc = db.query(KYC).filter(
        KYC.user_id == current_user.id
    ).order_by(
        KYC.created_at.desc(),
        KYC.id.desc()
    ).first()

    if not kyc:

        raise HTTPException(
            status_code=404,
            detail="KYC application not found"
        )

    return safe_kyc_response(kyc)

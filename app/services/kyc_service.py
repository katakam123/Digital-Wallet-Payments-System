
from fastapi import HTTPException

from sqlalchemy.orm import Session

from app.models.kyc import KYC
from app.models.wallet import Wallet
from app.models.user import User


def approve_kyc(
    db: Session,
    kyc_id: int
):

    kyc = db.query(KYC).filter(
        KYC.id == kyc_id
    ).with_for_update().first()

    if not kyc:
        raise HTTPException(
            status_code=404,
            detail="KYC application not found"
        )

    if kyc.status != "Pending":
        raise HTTPException(
            status_code=400,
            detail="Only pending KYC applications can be approved"
        )

    wallet = db.query(Wallet).filter(
        Wallet.owner_id == kyc.user_id
    ).with_for_update().first()

    user = db.query(User).filter(
        User.id == kyc.user_id
    ).with_for_update().first()

    if not wallet or not user:
        raise HTTPException(
            status_code=404,
            detail="User wallet or account not found"
        )

    kyc.status = "Approved"
    kyc.rejection_reason = None

    wallet.kyc_level = "Full"
    user.kyc_status = "Approved"

    db.commit()

    db.refresh(kyc)

    return kyc


def reject_kyc(
    db: Session,
    kyc_id: int,
    reason: str
):

    kyc = db.query(KYC).filter(
        KYC.id == kyc_id
    ).with_for_update().first()

    if not kyc:
        raise HTTPException(
            status_code=404,
            detail="KYC application not found"
        )

    if kyc.status != "Pending":
        raise HTTPException(
            status_code=400,
            detail="Only pending KYC applications can be rejected"
        )

    reason = reason.strip()

    if not reason:
        raise HTTPException(
            status_code=422,
            detail="Rejection reason is required"
        )

    user = db.query(User).filter(
        User.id == kyc.user_id
    ).with_for_update().first()

    kyc.status = "Rejected"
    kyc.rejection_reason = reason

    # Keep the wallet at Minimum KYC
    if user:
        user.kyc_status = "Rejected"

    db.commit()

    db.refresh(kyc)

    return kyc

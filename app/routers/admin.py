
from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)
from app.schemas.fraud_review import FraudDecisionSchema

from app.services.fraud_review_service import (
    list_flagged_transactions,
    approve_flagged_transaction,
    reject_flagged_transaction,
)
from sqlalchemy.orm import Session

from app.database import get_db

from app.models.wallet import Wallet
from app.models.kyc import KYC

from app.auth.security import require_admin

from app.schemas.kyc import (
    KYCResponse,
    KYCReviewSchema,
    KYCFreezeSchema
)

from app.services.kyc_service import (
    approve_kyc,
    reject_kyc
)

from app.routers.kyc import safe_kyc_response


router = APIRouter(
    prefix="/admin",
    tags=["Admin Management"]
)


# --------------------------------
# APPROVE KYC
# --------------------------------

@router.put(
    "/kyc/{kyc_id}/approve",
    response_model=KYCResponse
)
def admin_approve_kyc(
    kyc_id: int,
    db: Session = Depends(get_db),
    admin=Depends(require_admin)
):

    kyc = approve_kyc(
        db=db,
        kyc_id=kyc_id
    )

    return safe_kyc_response(kyc)


# --------------------------------
# REJECT KYC
# --------------------------------

@router.put(
    "/kyc/{kyc_id}/reject",
    response_model=KYCResponse
)
def admin_reject_kyc(
    kyc_id: int,
    data: KYCReviewSchema,
    db: Session = Depends(get_db),
    admin=Depends(require_admin)
):

    if not data.rejection_reason or not data.rejection_reason.strip():

        raise HTTPException(
            status_code=422,
            detail="Rejection reason is required"
        )

    kyc = reject_kyc(
        db=db,
        kyc_id=kyc_id,
        reason=data.rejection_reason
    )

    return safe_kyc_response(kyc)


# --------------------------------
# FREEZE WALLET
# --------------------------------

@router.put(
    "/wallets/{wallet_id}/freeze"
)
def freeze_wallet(
    wallet_id: int,
    data: KYCFreezeSchema,
    db: Session = Depends(get_db),
    admin=Depends(require_admin)
):

    reason = data.reason.strip()

    if len(reason) < 5:

        raise HTTPException(
            status_code=422,
            detail="A valid freeze reason is required"
        )

    wallet = db.query(Wallet).filter(
        Wallet.id == wallet_id
    ).with_for_update().first()

    if not wallet:

        raise HTTPException(
            status_code=404,
            detail="Wallet not found"
        )

    if wallet.status == "Frozen":

        raise HTTPException(
            status_code=400,
            detail="Wallet is already frozen"
        )

    try:

        wallet.status = "Frozen"
        wallet.freeze_reason = reason

        db.commit()
        db.refresh(wallet)

        return {
            "message": "Wallet frozen successfully",
            "wallet_id": wallet.id,
            "wallet_number": wallet.wallet_number,
            "status": wallet.status,
            "reason": wallet.freeze_reason
        }

    except Exception:

        db.rollback()
        raise


# --------------------------------
# UNFREEZE WALLET
# --------------------------------

@router.put(
    "/wallets/{wallet_id}/unfreeze"
)
def unfreeze_wallet(
    wallet_id: int,
    db: Session = Depends(get_db),
    admin=Depends(require_admin)
):

    wallet = db.query(Wallet).filter(
        Wallet.id == wallet_id
    ).with_for_update().first()

    if not wallet:

        raise HTTPException(
            status_code=404,
            detail="Wallet not found"
        )

    if wallet.status == "Active":

        raise HTTPException(
            status_code=400,
            detail="Wallet is already active"
        )

    try:

        wallet.status = "Active"
        wallet.freeze_reason = None

        db.commit()
        db.refresh(wallet)

        return {
            "message": "Wallet unfrozen successfully",
            "wallet_id": wallet.id,
            "wallet_number": wallet.wallet_number,
            "status": wallet.status
        }

    except Exception:

        db.rollback()
        raise
# ==============================================
# LIST FLAGGED TRANSACTIONS
# ==============================================

@router.get("/flagged-transactions")
def get_flagged_transactions(
    status: str = "Pending",
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=400,
            detail="Limit must be between 1 and 100.",
        )

    if offset < 0:
        raise HTTPException(
            status_code=400,
            detail="Offset cannot be negative.",
        )

    return list_flagged_transactions(
        db=db,
        status=status,
        limit=limit,
        offset=offset,
    )


# ==============================================
# APPROVE HELD TRANSACTION
# ==============================================

@router.put("/transactions/{transaction_ref}/approve")
def admin_approve_transaction(
    transaction_ref: str,
    data: FraudDecisionSchema,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    return approve_flagged_transaction(
        db=db,
        admin=admin,
        transaction_ref=transaction_ref,
        decision_reason=data.decision_reason,
    )


# ==============================================
# REJECT HELD TRANSACTION
# ==============================================

@router.put("/transactions/{transaction_ref}/reject")
def admin_reject_transaction(
    transaction_ref: str,
    data: FraudDecisionSchema,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    if not data.decision_reason or len(data.decision_reason.strip()) < 3:
        raise HTTPException(
            status_code=422,
            detail="Rejection reason is required.",
        )

    return reject_flagged_transaction(
        db=db,
        admin=admin,
        transaction_ref=transaction_ref,
        decision_reason=data.decision_reason,
    )
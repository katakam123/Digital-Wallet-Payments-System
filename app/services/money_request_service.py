from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.wallet import Wallet
from app.models.money_request import MoneyRequest

from app.services.ledger_service import money
from app.services.transfer_service import execute_transfer


REQUEST_EXPIRY_HOURS = 48
MAX_PENDING_REQUESTS = 5
MINIMUM_REQUEST_AMOUNT = Decimal("1.00")


def utc_now_naive():
    """
    Return current UTC time without timezone information.

    MySQL commonly returns naive datetimes even when
    DateTime(timezone=True) is used.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def expire_request_if_needed(
    db: Session,
    money_request: MoneyRequest,
) -> bool:
    """Expire one pending request if its expiry time has passed."""

    now = utc_now_naive()

    expires_at = money_request.expires_at

    if expires_at.tzinfo is not None:
        expires_at = expires_at.astimezone(
            timezone.utc
        ).replace(tzinfo=None)

    if (
        money_request.status == "Pending"
        and expires_at <= now
    ):
        money_request.status = "Expired"
        db.commit()
        db.refresh(money_request)
        return True

    return False


def expire_old_requests(
    db: Session,
    user_id: Optional[int] = None,
):
    """Mark expired pending requests as Expired."""

    now = utc_now_naive()

    query = db.query(MoneyRequest).filter(
        MoneyRequest.status == "Pending",
        MoneyRequest.expires_at <= now,
    )

    if user_id is not None:
        query = query.filter(
            or_(
                MoneyRequest.requester_id == user_id,
                MoneyRequest.payer_id == user_id,
            )
        )

    query.update(
        {"status": "Expired"},
        synchronize_session=False,
    )


def create_money_request(
    db: Session,
    current_user: User,
    payer_phone: str,
    amount: Decimal,
    note: Optional[str] = None,
):
    """Create a request asking another user to send money."""

    try:
        amount = money(amount)
    except (ValueError, TypeError, ArithmeticError):
        raise HTTPException(
            status_code=422,
            detail="Invalid amount. Use a maximum of two decimal places.",
        )

    if amount < MINIMUM_REQUEST_AMOUNT:
        raise HTTPException(
            status_code=400,
            detail="Minimum money request amount is ₹1.",
        )

    if current_user.phone == payer_phone:
        raise HTTPException(
            status_code=400,
            detail="You cannot request money from yourself.",
        )

    payer = (
        db.query(User)
        .filter(
            User.phone == payer_phone,
            User.is_active.is_(True),
        )
        .first()
    )

    if not payer:
        raise HTTPException(
            status_code=404,
            detail="Payer not found or payer account is inactive.",
        )

    # Lock both user records in a consistent order.
    user_ids = sorted([current_user.id, payer.id])

    locked_users = (
        db.query(User)
        .filter(User.id.in_(user_ids))
        .order_by(User.id)
        .with_for_update()
        .all()
    )

    user_map = {user.id: user for user in locked_users}

    requester = user_map.get(current_user.id)
    payer = user_map.get(payer.id)

    if not requester or not payer:
        raise HTTPException(
            status_code=404,
            detail="Requester or payer account was not found.",
        )

    if not requester.is_active or not payer.is_active:
        raise HTTPException(
            status_code=403,
            detail="Both accounts must be active.",
        )

    # A payer must have a wallet to pay the request.
    payer_wallet = (
        db.query(Wallet)
        .filter(Wallet.owner_id == payer.id)
        .first()
    )

    if not payer_wallet:
        raise HTTPException(
            status_code=404,
            detail="The selected payer does not have a wallet.",
        )

    # Expire old requests before checking the pending-request limit.
    expire_old_requests(
        db,
        user_id=requester.id,
    )

    pending_count = (
        db.query(MoneyRequest)
        .filter(
            MoneyRequest.requester_id == requester.id,
            MoneyRequest.payer_id == payer.id,
            MoneyRequest.status == "Pending",
        )
        .count()
    )

    if pending_count >= MAX_PENDING_REQUESTS:
        raise HTTPException(
            status_code=400,
            detail=(
                "You already have five pending requests "
                "for this person. Wait until one is completed, "
                "declined, cancelled, or expired."
            ),
        )

    money_request = MoneyRequest(
        requester_id=requester.id,
        payer_id=payer.id,
        amount=amount,
        note=note,
        status="Pending",
        expires_at=(
            datetime.now(timezone.utc)
            + timedelta(hours=REQUEST_EXPIRY_HOURS)
        ),
    )

    db.add(money_request)
    db.commit()
    db.refresh(money_request)

    return money_request


def get_money_requests(
    db: Session,
    current_user: User,
    direction: str = "all",
    status: Optional[str] = None,
):
    """Get incoming, outgoing, or all requests for the logged-in user."""

    valid_directions = ["all", "incoming", "outgoing"]

    if direction not in valid_directions:
        raise HTTPException(
            status_code=400,
            detail="Direction must be all, incoming, or outgoing.",
        )

    valid_statuses = [
        "Pending",
        "Paid",
        "Declined",
        "Cancelled",
        "Expired",
    ]

    if status and status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail="Invalid money request status.",
        )

    expire_old_requests(
        db,
        user_id=current_user.id,
    )

    query = db.query(MoneyRequest)

    if direction == "incoming":
        query = query.filter(
            MoneyRequest.payer_id == current_user.id
        )

    elif direction == "outgoing":
        query = query.filter(
            MoneyRequest.requester_id == current_user.id
        )

    else:
        query = query.filter(
            or_(
                MoneyRequest.requester_id == current_user.id,
                MoneyRequest.payer_id == current_user.id,
            )
        )

    if status:
        query = query.filter(
            MoneyRequest.status == status
        )

    requests = (
        query
        .order_by(MoneyRequest.created_at.desc())
        .all()
    )

    return {
        "total": len(requests),
        "requests": requests,
    }


def pay_money_request(
    db: Session,
    current_user: User,
    request_id: int,
    pin: str,
    otp: Optional[str] = None,
):
    """Pay a request using the existing Send Money implementation."""

    money_request = (
        db.query(MoneyRequest)
        .filter(MoneyRequest.id == request_id)
        .with_for_update()
        .first()
    )

    if not money_request:
        raise HTTPException(
            status_code=404,
            detail="Money request not found.",
        )

    if money_request.payer_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Only the requested payer can pay this request.",
        )

    if money_request.status != "Pending":
        raise HTTPException(
            status_code=400,
            detail=(
                f"This request cannot be paid because its status "
                f"is {money_request.status}."
            ),
        )

    if expire_request_if_needed(db, money_request):
        raise HTTPException(
            status_code=400,
            detail="This money request has expired.",
        )

    requester = (
        db.query(User)
        .filter(User.id == money_request.requester_id)
        .first()
    )

    if not requester:
        raise HTTPException(
            status_code=404,
            detail="Requester account was not found.",
        )

    try:
        # Reuse the existing Send Money rules.
        # commit=False allows us to update the request status
        # before committing both changes together.
        transfer_result = execute_transfer(
            db=db,
            current_user=current_user,
            receiver_phone=requester.phone,
            amount=money_request.amount,
            note=money_request.note or "Money request payment",
            pin=pin,
            otp=otp,
            commit=False,
        )

        money_request.status = "Paid"

        # Transfer and request status are committed together.
        db.commit()
        db.refresh(money_request)

        return {
            "message": "Money request paid successfully.",
            "money_request": money_request,
            "transaction_ref": transfer_result["transaction_ref"],
            "amount": transfer_result["amount"],
        }

    except Exception:
        db.rollback()
        raise


def decline_money_request(
    db: Session,
    current_user: User,
    request_id: int,
):
    """Only the payer can decline a money request."""

    money_request = (
        db.query(MoneyRequest)
        .filter(MoneyRequest.id == request_id)
        .with_for_update()
        .first()
    )

    if not money_request:
        raise HTTPException(
            status_code=404,
            detail="Money request not found.",
        )

    if money_request.payer_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Only the requested payer can decline this request.",
        )

    if money_request.status != "Pending":
        raise HTTPException(
            status_code=400,
            detail="Only pending requests can be declined.",
        )

    if expire_request_if_needed(db, money_request):
        raise HTTPException(
            status_code=400,
            detail="This money request has expired.",
        )

    money_request.status = "Declined"

    db.commit()
    db.refresh(money_request)

    return {
        "message": "Money request declined successfully.",
        "money_request": money_request,
    }


def cancel_money_request(
    db: Session,
    current_user: User,
    request_id: int,
):
    """Only the requester can cancel a money request."""

    money_request = (
        db.query(MoneyRequest)
        .filter(MoneyRequest.id == request_id)
        .with_for_update()
        .first()
    )

    if not money_request:
        raise HTTPException(
            status_code=404,
            detail="Money request not found.",
        )

    if money_request.requester_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Only the requester can cancel this request.",
        )

    if money_request.status != "Pending":
        raise HTTPException(
            status_code=400,
            detail="Only pending requests can be cancelled.",
        )

    if expire_request_if_needed(db, money_request):
        raise HTTPException(
            status_code=400,
            detail="This money request has expired.",
        )

    money_request.status = "Cancelled"

    db.commit()
    db.refresh(money_request)

    return {
        "message": "Money request cancelled successfully.",
        "money_request": money_request,
    }
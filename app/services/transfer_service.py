
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.wallet import Wallet
from app.models.otp import OTP
from app.models.financial_transaction import FinancialTransaction
from app.models.fraud_review import FraudReview

from app.services.pin_otp_service import verify_secret

from app.services.ledger_service import (
    money,
    get_system_account,
    get_or_create_wallet_account,
    post_transaction,
)


# ==================================================
# CONSTANTS
# ==================================================

INDIA_TZ = ZoneInfo("Asia/Kolkata")

HIGH_VALUE_LIMIT = Decimal("5000.00")
FRAUD_AMOUNT_LIMIT = Decimal("20000.00")

FRAUD_TRANSFER_COUNT_LIMIT = 5
FRAUD_TIME_WINDOW_SECONDS = 60

KYC_LIMITS = {
    "Minimum": {
        "wallet": Decimal("10000.00"),
        "daily": Decimal("10000.00"),
        "monthly": Decimal("25000.00"),
    },
    "Full": {
        "wallet": Decimal("200000.00"),
        "daily": Decimal("25000.00"),
        "monthly": Decimal("100000.00"),
    },
}

OUTGOING_TRANSACTION_TYPES = [
    "Transfer",
    "Merchant Payment",
    "Withdrawal",
]


# ==================================================
# DATETIME HELPERS
# ==================================================

def utc_now():
    return datetime.now(timezone.utc)


def database_datetime(value):
    """Normalize a database datetime to aware UTC."""

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def get_indian_period_boundaries():
    """Return today's and this month's start times as naive UTC."""

    now = datetime.now(INDIA_TZ)

    day_start = now.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    month_start = now.replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    return (
        day_start.astimezone(timezone.utc).replace(tzinfo=None),
        month_start.astimezone(timezone.utc).replace(tzinfo=None),
    )


# ==================================================
# OUTGOING SPENDING LIMITS
# ==================================================

def get_outgoing_total(
    db: Session,
    user_id: int,
    start_time: datetime,
) -> Decimal:

    total = (
        db.query(
            func.coalesce(
                func.sum(FinancialTransaction.amount),
                0,
            )
        )
        .filter(
            FinancialTransaction.initiated_by == user_id,
            FinancialTransaction.status.in_(
                ["Success", "On Hold"]
            ),
            FinancialTransaction.type.in_(
                OUTGOING_TRANSACTION_TYPES
            ),
            FinancialTransaction.created_at >= start_time,
        )
        .scalar()
    )

    return Decimal(str(total or "0.00"))


def check_spending_limits(
    db: Session,
    user: User,
    wallet: Wallet,
    amount: Decimal,
):

    limits = KYC_LIMITS.get(wallet.kyc_level)

    if not limits:
        raise HTTPException(
            status_code=400,
            detail="Your wallet has an unsupported KYC level.",
        )

    day_start, month_start = get_indian_period_boundaries()

    daily_spent = get_outgoing_total(
        db,
        user.id,
        day_start,
    )

    monthly_spent = get_outgoing_total(
        db,
        user.id,
        month_start,
    )

    daily_remaining = max(
        Decimal("0.00"),
        limits["daily"] - daily_spent,
    )

    monthly_remaining = max(
        Decimal("0.00"),
        limits["monthly"] - monthly_spent,
    )

    if amount > daily_remaining:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Daily limit of ₹{limits['daily']:,.2f}. "
                f"You can send ₹{daily_remaining:,.2f} more today. "
                "This transfer exceeds your remaining daily limit."
            ),
        )

    if amount > monthly_remaining:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Monthly limit of ₹{limits['monthly']:,.2f}. "
                f"You can send ₹{monthly_remaining:,.2f} more this month. "
                "This transfer exceeds your remaining monthly limit."
            ),
        )


# ==================================================
# PIN VERIFICATION
# ==================================================

def verify_transfer_pin(
    db: Session,
    user: User,
    pin: str,
):

    now = utc_now()

    if user.pin_locked_until:

        locked_until = database_datetime(
            user.pin_locked_until
        )

        if locked_until > now:

            remaining = int(
                (locked_until - now).total_seconds()
            )

            raise HTTPException(
                status_code=403,
                detail=(
                    "Payments are locked because of incorrect PIN attempts. "
                    f"Try again in approximately {remaining} seconds."
                ),
            )

        user.pin_locked_until = None
        user.pin_failed_attempts = 0

    if not user.transaction_pin_hash:
        raise HTTPException(
            status_code=400,
            detail="Please set your transaction PIN before sending money.",
        )

    if not verify_secret(
        pin,
        user.transaction_pin_hash,
    ):

        user.pin_failed_attempts += 1

        if user.pin_failed_attempts >= 3:
            user.pin_locked_until = (
                now + timedelta(minutes=30)
            )

        # Preserve failed attempts.
        db.commit()

        if user.pin_failed_attempts >= 3:
            raise HTTPException(
                status_code=403,
                detail="Incorrect PIN. Payments are locked for 30 minutes.",
            )

        raise HTTPException(
            status_code=401,
            detail=(
                "Incorrect transaction PIN. "
                f"{3 - user.pin_failed_attempts} attempt(s) remaining."
            ),
        )

    # Successful PIN verification is saved with the transfer.
    user.pin_failed_attempts = 0
    user.pin_locked_until = None


# ==================================================
# OTP VERIFICATION
# ==================================================

def verify_transfer_otp(
    db: Session,
    user: User,
    otp_code: str,
):

    now = utc_now()

    otp_record = (
        db.query(OTP)
        .filter(
            OTP.user_id == user.id,
            OTP.purpose == "High Value Transfer",
            OTP.is_used.is_(False),
        )
        .order_by(OTP.created_at.desc())
        .with_for_update()
        .first()
    )

    if not otp_record:
        raise HTTPException(
            status_code=400,
            detail="No valid transfer OTP found. Request a new OTP.",
        )

    expiry = database_datetime(
        otp_record.expires_at
    )

    if expiry <= now:

        otp_record.is_used = True
        db.commit()

        raise HTTPException(
            status_code=400,
            detail="Transfer OTP has expired. Request a new OTP.",
        )

    if otp_record.attempts >= 3:

        otp_record.is_used = True
        db.commit()

        raise HTTPException(
            status_code=400,
            detail="OTP attempts exceeded. Request a new OTP.",
        )

    if not verify_secret(
        otp_code,
        otp_record.otp_hash,
    ):

        otp_record.attempts += 1

        if otp_record.attempts >= 3:
            otp_record.is_used = True

        db.commit()

        raise HTTPException(
            status_code=400,
            detail=(
                "Incorrect OTP. "
                f"{3 - otp_record.attempts} attempt(s) remaining."
            ),
        )

    # OTP is consumed with the transfer transaction.
    otp_record.is_used = True


# ==================================================
# FRAUD DETECTION
# ==================================================

def detect_transfer_fraud(
    db: Session,
    user_id: int,
    amount: Decimal,
) -> list[str]:
    """
    Detect suspicious outgoing transfers.

    Rule 1:
        More than 5 transfers within 60 seconds.

    Rule 2:
        A single transfer above ₹20,000.

    The current transfer has not yet been inserted.
    """

    reasons = []

    cutoff = (
        utc_now() - timedelta(
            seconds=FRAUD_TIME_WINDOW_SECONDS
        )
    ).replace(tzinfo=None)

    recent_count = (
        db.query(
            func.count(FinancialTransaction.id)
        )
        .filter(
            FinancialTransaction.initiated_by == user_id,
            FinancialTransaction.type == "Transfer",
            FinancialTransaction.created_at >= cutoff,
        )
        .scalar()
        or 0
    )

    # Five previous transfers plus this transfer
    # means six transfers within the time window.
    if recent_count >= FRAUD_TRANSFER_COUNT_LIMIT:

        reasons.append(
            "More than 5 outgoing transfers within 1 minute."
        )

    if amount > FRAUD_AMOUNT_LIMIT:

        reasons.append(
            "Single transfer amount exceeds ₹20,000."
        )

    return reasons


# ==================================================
# EXECUTE TRANSFER
# ==================================================

def execute_transfer(
    db: Session,
    current_user: User,
    receiver_phone: str,
    amount: Decimal,
    note: str | None,
    pin: str,
    otp: str | None,
    commit: bool = True,
):

    try:

        amount = money(amount)

    except (ValueError, TypeError, ArithmeticError):

        raise HTTPException(
            status_code=422,
            detail="Invalid amount. Use a maximum of two decimal places.",
        )

    if amount < Decimal("1.00"):

        raise HTTPException(
            status_code=400,
            detail="Minimum transfer amount is ₹1.",
        )

    if current_user.phone == receiver_phone:

        raise HTTPException(
            status_code=400,
            detail="You cannot send money to yourself.",
        )

    try:

        # ------------------------------------------
        # 1. FIND RECEIVER
        # ------------------------------------------

        receiver = (
            db.query(User)
            .filter(
                User.phone == receiver_phone,
                User.is_active.is_(True),
            )
            .first()
        )

        if not receiver:

            raise HTTPException(
                status_code=404,
                detail="Receiver not found or receiver account is inactive.",
            )

        if receiver.id == current_user.id:

            raise HTTPException(
                status_code=400,
                detail="You cannot send money to yourself.",
            )

        # ------------------------------------------
        # 2. FIND WALLETS
        # ------------------------------------------

        sender_wallet_id = (
            db.query(Wallet.id)
            .filter(
                Wallet.owner_id == current_user.id
            )
            .scalar()
        )

        receiver_wallet_id = (
            db.query(Wallet.id)
            .filter(
                Wallet.owner_id == receiver.id
            )
            .scalar()
        )

        if sender_wallet_id is None:

            raise HTTPException(
                status_code=404,
                detail="Your wallet was not found.",
            )

        if receiver_wallet_id is None:

            raise HTTPException(
                status_code=404,
                detail="Receiver wallet was not found.",
            )

        # ------------------------------------------
        # 3. LOCK WALLETS IN CONSISTENT ORDER
        # ------------------------------------------

        wallet_ids = sorted({
            sender_wallet_id,
            receiver_wallet_id,
        })

        locked_wallets = (
            db.query(Wallet)
            .filter(
                Wallet.id.in_(wallet_ids)
            )
            .order_by(Wallet.id)
            .with_for_update()
            .all()
        )

        wallet_map = {
            wallet.id: wallet
            for wallet in locked_wallets
        }

        sender_wallet = wallet_map.get(
            sender_wallet_id
        )

        receiver_wallet = wallet_map.get(
            receiver_wallet_id
        )

        if not sender_wallet or not receiver_wallet:

            raise HTTPException(
                status_code=404,
                detail="Sender or receiver wallet not found.",
            )

        # ------------------------------------------
        # 4. CHECK WALLET STATUS
        # ------------------------------------------

        if sender_wallet.status != "Active":

            raise HTTPException(
                status_code=403,
                detail="Your wallet is not active.",
            )

        if receiver_wallet.status != "Active":

            raise HTTPException(
                status_code=400,
                detail="Receiver wallet is not active.",
            )

        # ------------------------------------------
        # 5. LOCK USER RECORDS
        # ------------------------------------------

        locked_users = (
            db.query(User)
            .filter(
                User.id.in_(
                    sorted([
                        current_user.id,
                        receiver.id,
                    ])
                )
            )
            .order_by(User.id)
            .with_for_update()
            .all()
        )

        user_map = {
            user.id: user
            for user in locked_users
        }

        sender = user_map.get(current_user.id)
        receiver_user = user_map.get(receiver.id)

        if not sender or not receiver_user:

            raise HTTPException(
                status_code=404,
                detail="Sender or receiver account not found.",
            )

        if not sender.is_active:

            raise HTTPException(
                status_code=403,
                detail="Your account is inactive.",
            )

        if not receiver_user.is_active:

            raise HTTPException(
                status_code=400,
                detail="Receiver account is inactive.",
            )

        # ------------------------------------------
        # 6. CHECK BALANCE
        # ------------------------------------------

        if sender_wallet.balance < amount:

            raise HTTPException(
                status_code=400,
                detail=(
                    f"Insufficient balance. Your available balance is "
                    f"₹{sender_wallet.balance:,.2f}."
                ),
            )

        # ------------------------------------------
        # 7. CHECK RECEIVER WALLET CAPACITY
        # ------------------------------------------

        receiver_limits = KYC_LIMITS.get(
            receiver_wallet.kyc_level
        )

        if not receiver_limits:

            raise HTTPException(
                status_code=400,
                detail="Receiver has an unsupported KYC level.",
            )

        if (
            receiver_wallet.balance + amount
            > receiver_limits["wallet"]
        ):

            remaining_capacity = max(
                Decimal("0.00"),
                receiver_limits["wallet"]
                - receiver_wallet.balance,
            )

            raise HTTPException(
                status_code=400,
                detail=(
                    "Receiver's KYC wallet balance limit would be exceeded. "
                    f"Receiver can accept ₹{remaining_capacity:,.2f} more."
                ),
            )

        # ------------------------------------------
        # 8. CHECK SPENDING LIMITS
        # ------------------------------------------

        check_spending_limits(
            db=db,
            user=sender,
            wallet=sender_wallet,
            amount=amount,
        )

        # ------------------------------------------
        # 9. VERIFY PIN
        # ------------------------------------------

        verify_transfer_pin(
            db=db,
            user=sender,
            pin=pin,
        )

        # ------------------------------------------
        # 10. VERIFY OTP ABOVE ₹5,000
        # ------------------------------------------

        if amount > HIGH_VALUE_LIMIT:

            if not otp:

                raise HTTPException(
                    status_code=400,
                    detail="OTP is required for transfers above ₹5,000.",
                )

            verify_transfer_otp(
                db=db,
                user=sender,
                otp_code=otp,
            )

        # ------------------------------------------
        # 11. DETECT FRAUD
        # ------------------------------------------

        fraud_reasons = detect_transfer_fraud(
            db=db,
            user_id=sender.id,
            amount=amount,
        )

        is_on_hold = bool(fraud_reasons)

        # ------------------------------------------
        # 12. GET SENDER LEDGER ACCOUNT
        # ------------------------------------------

        sender_role = getattr(
            sender.role,
            "value",
            sender.role,
        )

        sender_account_type = (
            "Merchant Wallet"
            if sender_role == "Merchant"
            else "User Wallet"
        )

        sender_account = get_or_create_wallet_account(
            db=db,
            wallet=sender_wallet,
            account_type=sender_account_type,
        )

        # ------------------------------------------
        # 13. FRAUD TRANSFER: SEND TO HOLD
        # ------------------------------------------

        if is_on_hold:

            hold_account = get_system_account(
                db=db,
                system_code="HOLD",
            )

            transaction = post_transaction(
                db=db,
                initiated_by=sender.id,
                transaction_type="Transfer",
                amount=amount,
                postings=[
                    (
                        sender_account.id,
                        "Debit",
                        amount,
                    ),
                    (
                        hold_account.id,
                        "Credit",
                        amount,
                    ),
                ],
                description=(
                    f"Transfer to {receiver_user.phone}. "
                    f"On Hold: {' '.join(fraud_reasons)}"
                ),
                is_flagged=True,
                initial_status="On Hold",
                commit=False,
            )

            # Save the fraud review.
            review = FraudReview(
                transaction_id=transaction.id,
                sender_user_id=sender.id,
                receiver_user_id=receiver_user.id,
                flag_reason=" ".join(fraud_reasons),
                status="Pending",
            )

            db.add(review)

            if commit:
                db.commit()
                db.refresh(transaction)
            else:
                db.flush()

            message = (
                "Transfer submitted but placed On Hold for security review. "
                "The receiver has not received the money."
            )

        # ------------------------------------------
        # 14. NORMAL TRANSFER
        # ------------------------------------------

        else:

            receiver_role = getattr(
                receiver_user.role,
                "value",
                receiver_user.role,
            )

            receiver_account_type = (
                "Merchant Wallet"
                if receiver_role == "Merchant"
                else "User Wallet"
            )

            receiver_account = get_or_create_wallet_account(
                db=db,
                wallet=receiver_wallet,
                account_type=receiver_account_type,
            )

            transaction = post_transaction(
                db=db,
                initiated_by=sender.id,
                transaction_type="Transfer",
                amount=amount,
                postings=[
                    (
                        sender_account.id,
                        "Debit",
                        amount,
                    ),
                    (
                        receiver_account.id,
                        "Credit",
                        amount,
                    ),
                ],
                description=(
                    f"Transfer to {receiver_user.phone}. "
                    f"Note: {note or 'No note'}"
                ),
                is_flagged=False,
                initial_status="Success",
                commit=False,
            )

            if commit:
                db.commit()
                db.refresh(transaction)
            else:
                db.flush()

            message = "Money transferred successfully."

        # ------------------------------------------
        # 15. RETURN TRANSFER RESPONSE
        # ------------------------------------------

        return {
            "transaction_ref": transaction.transaction_ref,
            "transaction_type": "Transfer",
            "amount": transaction.amount,
            "status": transaction.status,
            "sender_wallet_balance": sender_wallet.balance,
            "message": message,
        }

    except HTTPException:

        db.rollback()
        raise

    except Exception:

        db.rollback()
        raise

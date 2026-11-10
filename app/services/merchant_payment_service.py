
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.wallet import Wallet
from app.models.ledger_account import LedgerAccount
from app.models.cashback import Cashback

from app.services.ledger_service import (
    money,
    post_transaction,
    get_system_account,
)

from app.services.pin_otp_service import (
    verify_transaction_pin_for_payment,
    consume_otp_authorization,
)


ZERO = Decimal("0.00")
ONE_PERCENT = Decimal("0.01")
TWO_PERCENT = Decimal("0.02")
CASHBACK_CAP = Decimal("50.00")
MINIMUM_PAYMENT = Decimal("1.00")


def calculate_percentage(
    amount: Decimal,
    percentage: Decimal,
) -> Decimal:

    return (
        amount * percentage
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def execute_merchant_payment(
    db: Session,
    current_user: User,
    merchant_code: str,
    amount: Decimal,
    pin: str,
):
    try:
        amount = money(amount)

        if amount < MINIMUM_PAYMENT:
            raise HTTPException(
                status_code=400,
                detail="Minimum merchant payment is ₹1.00.",
            )

        # -----------------------------------------
        # 1. Lock customer user row
        # -----------------------------------------

        customer = (
            db.query(User)
            .filter(User.id == current_user.id)
            .with_for_update()
            .first()
        )

        if not customer:
            raise HTTPException(
                status_code=404,
                detail="Customer account not found.",
            )

        if not customer.is_active:
            raise HTTPException(
                status_code=403,
                detail="Your account is inactive.",
            )

        # -----------------------------------------
        # 2. Verify customer PIN
        # -----------------------------------------

        verify_transaction_pin_for_payment(
            db=db,
            user=customer,
            pin=pin,
        )

        # -----------------------------------------
        # 3. Find merchant
        # -----------------------------------------

        merchant = (
            db.query(User)
            .filter(
                User.merchant_code == merchant_code,
                User.role == "Merchant",
            )
            .first()
        )

        if not merchant:
            raise HTTPException(
                status_code=404,
                detail="Merchant not found.",
            )

        if not merchant.is_active:
            raise HTTPException(
                status_code=403,
                detail="Merchant account is inactive.",
            )

        if merchant.id == customer.id:
            raise HTTPException(
                status_code=400,
                detail="You cannot pay your own merchant account.",
            )

        # -----------------------------------------
        # 4. Find both wallets and lock them
        # -----------------------------------------

        customer_wallet = (
            db.query(Wallet)
            .filter(Wallet.owner_id == customer.id)
            .first()
        )

        merchant_wallet = (
            db.query(Wallet)
            .filter(Wallet.owner_id == merchant.id)
            .first()
        )

        if not customer_wallet or not merchant_wallet:
            raise HTTPException(
                status_code=404,
                detail="Customer or merchant wallet not found.",
            )

        wallet_ids = sorted([
            customer_wallet.id,
            merchant_wallet.id,
        ])

        locked_wallets = (
            db.query(Wallet)
            .filter(Wallet.id.in_(wallet_ids))
            .order_by(Wallet.id)
            .with_for_update()
            .all()
        )

        wallet_map = {
            wallet.id: wallet
            for wallet in locked_wallets
        }

        customer_wallet = wallet_map[customer_wallet.id]
        merchant_wallet = wallet_map[merchant_wallet.id]

        if customer_wallet.status != "Active":
            raise HTTPException(
                status_code=403,
                detail="Your wallet is not active.",
            )

        if merchant_wallet.status != "Active":
            raise HTTPException(
                status_code=403,
                detail="Merchant wallet is not active.",
            )

        if money(customer_wallet.balance) < amount:
            raise HTTPException(
                status_code=409,
                detail="Insufficient wallet balance.",
            )

        # -----------------------------------------
        # 5. Verify high-value payment OTP
        # -----------------------------------------

        if amount > Decimal("5000.00"):
            consume_otp_authorization(
                customer,
                "High Value Transfer",
            )

        # -----------------------------------------
        # 6. Find existing ledger accounts
        # -----------------------------------------

        customer_account = (
            db.query(LedgerAccount)
            .filter(
                LedgerAccount.wallet_id == customer_wallet.id,
                LedgerAccount.account_type == "User Wallet",
            )
            .first()
        )

        merchant_account = (
            db.query(LedgerAccount)
            .filter(
                LedgerAccount.wallet_id == merchant_wallet.id,
                LedgerAccount.account_type == "Merchant Wallet",
            )
            .first()
        )

        if not customer_account or not merchant_account:
            raise HTTPException(
                status_code=409,
                detail="Wallet ledger accounts are not initialized.",
            )

        fees_account = get_system_account(
            db,
            "FEES",
            lock=False,
        )

        # -----------------------------------------
        # 7. Calculate merchant fee
        # -----------------------------------------

        fee = calculate_percentage(
            amount,
            ONE_PERCENT,
        )

        merchant_received = amount - fee

        if merchant_received <= ZERO:
            raise HTTPException(
                status_code=400,
                detail="Invalid merchant payment amount.",
            )

        # -----------------------------------------
        # 8. Calculate cashback
        # -----------------------------------------

        cashback_amount = min(
            calculate_percentage(amount, TWO_PERCENT),
            CASHBACK_CAP,
        )

        # -----------------------------------------
        # 9. Prepare balanced ledger postings
        # -----------------------------------------

        postings = [
            (
                customer_account.id,
                "Debit",
                amount,
            ),
            (
                merchant_account.id,
                "Credit",
                merchant_received,
            ),
            (
                fees_account.id,
                "Credit",
                fee,
            ),
        ]

        # -----------------------------------------
        # 10. Post financial transaction
        # -----------------------------------------

        transaction = post_transaction(
            db=db,
            initiated_by=customer.id,
            transaction_type="Merchant Payment",
            amount=amount,
            postings=postings,
            description=(
                f"Payment to {merchant.business_name or merchant.full_name} "
                f"({merchant.merchant_code})"
            ),
            is_flagged=False,
            commit=False,
        )

        # -----------------------------------------
        # 11. Create pending cashback
        # -----------------------------------------

        cashback = Cashback(
            payment_transaction_id=transaction.id,
            customer_id=customer.id,
            merchant_id=merchant.id,
            amount=cashback_amount,
            status="Pending",
            available_at=(
                datetime.now(timezone.utc)
                + timedelta(hours=24)
            ),
        )

        db.add(cashback)

        # -----------------------------------------
        # 12. Commit everything together
        # -----------------------------------------

        db.commit()
        db.refresh(transaction)
        db.refresh(cashback)

        return {
            "transaction_ref": transaction.transaction_ref,
            "status": transaction.status,
            "merchant_code": merchant.merchant_code,
            "merchant_name": (
                merchant.business_name or merchant.full_name
            ),
            "amount": amount,
            "merchant_fee": fee,
            "merchant_received": merchant_received,
            "cashback_amount": cashback_amount,
            "cashback_status": cashback.status,
            "message": "Merchant payment successful.",
        }

    except Exception:
        db.rollback()
        raise

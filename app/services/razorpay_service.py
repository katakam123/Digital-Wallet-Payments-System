
from decimal import Decimal, ROUND_HALF_UP

import razorpay
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.database import settings
from app.models.razorpay_payment import RazorpayPayment


def get_razorpay_client():
    if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Razorpay test credentials are not configured",
        )

    return razorpay.Client(
        auth=(
            settings.RAZORPAY_KEY_ID,
            settings.RAZORPAY_KEY_SECRET,
        )
    )


def rupees_to_paise(amount: Decimal) -> int:
    rounded = amount.quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )
    return int(rounded * 100)


def create_razorpay_order(
    db: Session,
    current_user,
    amount: Decimal,
):
    if amount < Decimal("1.00"):
        raise HTTPException(
            status_code=400,
            detail="Minimum add-money amount is ₹1",
        )

    if amount > Decimal("100000.00"):
        raise HTTPException(
            status_code=400,
            detail="Maximum test payment amount is ₹1,00,000",
        )

    client = get_razorpay_client()
    amount_paise = rupees_to_paise(amount)

    try:
        order = client.order.create({
            "amount": amount_paise,
            "currency": "INR",
            "receipt": f"wallet_{current_user.id}_{id(current_user)}",
            "notes": {
                "user_id": str(current_user.id),
                "purpose": "Wallet Add Money",
            },
        })
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="Could not create Razorpay order",
        ) from exc

    payment = RazorpayPayment(
        user_id=current_user.id,
        amount=amount,
        currency="INR",
        razorpay_order_id=order["id"],
        status="Created",
    )

    db.add(payment)
    db.commit()
    db.refresh(payment)

    return {
        "order_id": order["id"],
        "amount": amount_paise,
        "currency": "INR",
        "key_id": settings.RAZORPAY_KEY_ID,
    }


def verify_razorpay_signature(
    order_id: str,
    payment_id: str,
    signature: str,
):
    client = get_razorpay_client()

    try:
        client.utility.verify_payment_signature({
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": signature,
        })
        return True

    except Exception:
        return False

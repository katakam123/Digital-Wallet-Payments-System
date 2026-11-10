
from io import BytesIO

import qrcode

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.auth.security import require_user_or_merchant


router = APIRouter(
    prefix="/merchants",
    tags=["Merchants"],
)


# GET MERCHANT QR CODE
@router.get("/me/qr")
def get_my_merchant_qr(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_or_merchant),
):
    # Only merchants can access this endpoint.
    if current_user.role != "Merchant":
        raise HTTPException(
            status_code=403,
            detail="Only merchants can access their QR code.",
        )

    if not current_user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Your account is inactive.",
        )

    if not current_user.merchant_code:
        raise HTTPException(
            status_code=400,
            detail="Merchant code is not available. Contact the administrator.",
        )

    # Generate QR code containing the merchant code.
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )

    qr.add_data(current_user.merchant_code)
    qr.make(fit=True)

    image = qr.make_image(
        fill_color="black",
        back_color="white",
    )

    image_buffer = BytesIO()
    image.save(image_buffer, format="PNG")
    image_buffer.seek(0)

    return StreamingResponse(
        image_buffer,
        media_type="image/png",
        headers={
            "Content-Disposition": (
                f'inline; filename="{current_user.merchant_code}_QR.png"'
            )
        },
    )

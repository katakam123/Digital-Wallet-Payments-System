
from decimal import Decimal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    BackgroundTasks,
)

from fastapi.security import OAuth2PasswordRequestForm

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database import get_db, settings

from app.models.user import User
from app.models.wallet import Wallet

from app.services.ledger_service import (
    get_or_create_wallet_account,
)

from app.schemas.auth import (
    RegisterSchema,
    UserResponse,
    TokenResponse,
)

from app.auth.security import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
)

from app.services.email_service import send_login_alert


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


# ==================================================
# MERCHANT CODE GENERATOR
# ==================================================

def generate_merchant_code(user_id: int) -> str:
    """
    Generate a stable merchant code using the user ID.

    Examples:
        User ID 1  -> MER-10001
        User ID 45 -> MER-10045
    """

    return f"MER-{10000 + user_id:05d}"


# ==================================================
# REGISTER
# ==================================================

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    data: RegisterSchema,
    db: Session = Depends(get_db),
):
    email = str(data.email).strip().lower()

    # ----------------------------------------------
    # 1. Validate public registration role
    # ----------------------------------------------

    if data.role not in ("User", "Merchant"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only User and Merchant registration is allowed.",
        )

    # ----------------------------------------------
    # 2. Validate merchant information
    # ----------------------------------------------

    if data.role == "Merchant":

        if not data.business_name or not data.business_name.strip():
            raise HTTPException(
                status_code=400,
                detail="Business name is required for merchant registration.",
            )

        if (
            not data.business_category
            or not data.business_category.strip()
        ):
            raise HTTPException(
                status_code=400,
                detail="Business category is required for merchant registration.",
            )

    # ----------------------------------------------
    # 3. Check existing email
    # ----------------------------------------------

    existing_user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered.",
        )

    try:

        # ------------------------------------------
        # 4. Create user
        # ------------------------------------------

        new_user = User(
            full_name=data.full_name,
            email=email,
            phone=data.phone,
            hashed_password=hash_password(data.password),
            role=data.role,
            business_name=(
                data.business_name.strip()
                if data.business_name
                else None
            ),
            business_category=(
                data.business_category.strip()
                if data.business_category
                else None
            ),
            merchant_code=None,
            is_active=True,
            kyc_status="Pending",
        )

        db.add(new_user)

        # Generate the database user ID.
        db.flush()

        # ------------------------------------------
        # 5. Generate merchant code
        # ------------------------------------------

        if new_user.role == "Merchant":

            new_user.merchant_code = generate_merchant_code(
                new_user.id
            )

            db.flush()

        # ------------------------------------------
        # 6. Create wallet
        # ------------------------------------------

        new_wallet = Wallet(
            owner_id=new_user.id,
            balance=Decimal("0.00"),
            kyc_level="Minimum",
            currency="INR",
            status="Active",
        )

        db.add(new_wallet)

        # IMPORTANT:
        # Flush the wallet before creating its ledger account.
        # This generates new_wallet.id.
        db.flush()

        # ------------------------------------------
        # 7. Create wallet ledger account
        # ------------------------------------------

        account_type = (
            "Merchant Wallet"
            if new_user.role == "Merchant"
            else "User Wallet"
        )

        get_or_create_wallet_account(
            db=db,
            wallet=new_wallet,
            account_type=account_type,
        )

        # ------------------------------------------
        # 8. Commit everything together
        # ------------------------------------------

        db.commit()

        db.refresh(new_user)

        return new_user

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Email, merchant code, or wallet already exists."
            ),
        )

    except Exception:
        db.rollback()
        raise


# ==================================================
# LOGIN
# ==================================================

@router.post(
    "/login",
    response_model=TokenResponse,
)
def login(
    background_tasks: BackgroundTasks,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):

    email = form_data.username.strip().lower()

    # ----------------------------------------------
    # 1. Find user
    # ----------------------------------------------

    user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    # ----------------------------------------------
    # 2. Verify credentials
    # ----------------------------------------------

    if not user or not verify_password(
        form_data.password,
        user.hashed_password,
    ):

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={
                "WWW-Authenticate": "Bearer"
            },
        )

    # ----------------------------------------------
    # 3. Check account status
    # ----------------------------------------------

    if not user.is_active:

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is inactive.",
        )

    # ----------------------------------------------
    # 4. Generate JWT access token
    # ----------------------------------------------

    access_token = create_access_token(user.id)

    # ----------------------------------------------
    # 5. Send login alert email
    # ----------------------------------------------

    background_tasks.add_task(
        send_login_alert,
        user.email,
        user.full_name,
    )

    # ----------------------------------------------
    # 6. Return login response
    # ----------------------------------------------

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": (
            settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        ),
        "user": user,
    }


# ==================================================
# CURRENT USER
# ==================================================

@router.get(
    "/me",
    response_model=UserResponse,
)
def get_me(
    current_user: User = Depends(get_current_user),
):

    return current_user


from fastapi import FastAPI

from app.database import settings

from app.routers import auth
from app.routers import wallet
from app.routers import kyc
from app.routers import admin
from app.routers import pin, otp
from app.database import SessionLocal
from app.services.ledger_service import create_system_accounts
from app.routers import transfers
from app.routers import merchants
from app.routers import payments
from app.services.cashback_scheduler import (
    start_cashback_scheduler,
    stop_cashback_scheduler,
)
from app.routers import refunds
from app.routers import merchant_history
from app.routers import merchant_dashboard
from app.routers import merchant_exports
from app.routers import money_requests
from app.routers import bank_accounts
from app.routers import withdrawals
from app.routers import websockets
from app.routers import razorpay

app = FastAPI(
    title=settings.APP_NAME,
    description="Digital Wallet and Payments Backend",
    version="1.0.0"
)


app.include_router(auth.router)
app.include_router(wallet.router)
app.include_router(kyc.router)
app.include_router(admin.router)
app.include_router(pin.router)
app.include_router(otp.router)
app.include_router(transfers.router)
app.include_router(merchants.router)
app.include_router(payments.router)
app.include_router(refunds.router)
app.include_router(merchant_history.router)
app.include_router(merchant_dashboard.router)
app.include_router(merchant_exports.router)
app.include_router(money_requests.router)
app.include_router(bank_accounts.router)
app.include_router(withdrawals.router)
app.include_router(websockets.router)
app.include_router(razorpay.router)

@app.get("/")
def root():

    return {
        "message": "Digital Wallet API is running",
        "status": "success"
    }


@app.get("/health")
def health():

    return {
        "status": "healthy"
    }

@app.on_event("startup")
def initialize_ledger_accounts():
    db = SessionLocal()

    try:
        create_system_accounts(db)
        print("System ledger accounts initialized.")

    finally:
        db.close()

    start_cashback_scheduler()


@app.on_event("shutdown")
def shutdown_cashback_scheduler():
    stop_cashback_scheduler()


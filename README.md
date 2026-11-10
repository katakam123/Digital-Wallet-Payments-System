# Digital Wallet & Payments System

A secure, backend-based Digital Wallet and Payments Management System built using **FastAPI, Python, MySQL, SQLAlchemy, and Alembic**. The application provides wallet management, peer-to-peer money transfers, merchant payments, refunds, cashback, KYC verification, transaction PIN and OTP security, fraud detection, and withdrawal management.

---

## Project Overview

The Digital Wallet & Payments System is designed to simulate the core backend functionality of digital payment platforms such as Paytm and PhonePe.

Users can register, create wallets, add money, transfer money, pay merchants, request money, and view transaction records. Merchants can receive payments and process refunds. Administrators can manage KYC verification, freeze wallets, and review suspicious transactions.

The system uses a double-entry ledger accounting approach to maintain financial transaction consistency.

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Backend programming language |
| FastAPI | REST API framework |
| Pydantic | Request and response validation |
| SQLAlchemy | ORM and database operations |
| MySQL | Relational database |
| Alembic | Database migrations |
| JWT | Authentication and authorization |
| Passlib / bcrypt | Password and PIN hashing |
| APScheduler | Scheduled background jobs |
| FastAPI BackgroundTasks | Background processing |
| SMTP | Email notifications |
| QR Code | Merchant payment QR codes |
| ReportLab | PDF statement generation |
| Redis | Optional caching and temporary operations, where configured |
| Uvicorn | ASGI server |

## Main Features

### 1. Authentication and User Management

- User registration and login.
- Merchant registration.
- Admin account management.
- JWT access-token authentication.
- Role-based access control.
- Password hashing using bcrypt.
- User account activation and deactivation.

**Supported roles:**
- Admin
- User
- Merchant

### 2. Digital Wallet Management

- Automatic wallet creation after registration.
- Unique wallet number generation.
- Wallet balance management.
- Wallet balance checking.
- Wallet status management.
- Wallet freezing and unfreezing.
- INR currency support.

### 3. KYC Verification

Two wallet KYC levels are supported.

| Feature | Minimum KYC | Full KYC |
|---|---:|---:|
| Maximum wallet balance | ₹10,000 | ₹2,00,000 |
| Daily outgoing limit | ₹10,000 | ₹25,000 |
| Monthly outgoing limit | ₹25,000 | ₹1,00,000 |
| Bank withdrawal | Not allowed | Allowed |

Admin can approve or reject KYC applications.

### 4. Money Transfers

- Send money using a registered phone number.
- Receive money into a wallet.
- Transaction PIN verification.
- OTP verification for transfers above ₹5,000.
- Daily and monthly spending-limit validation.
- Insufficient-balance validation.
- Transaction history.
- Double-entry ledger accounting.

### 5. Transaction PIN and OTP Security

**Transaction PIN**
- Four-digit transaction PIN.
- PIN stored as a hash.
- Simple PIN combinations are restricted.
- Three incorrect attempts trigger a 30-minute payment lock.

**OTP**
- Six-digit OTP.
- OTP stored as a hash.
- Five-minute expiration.
- Maximum three verification attempts.
- 60-second resend restriction.
- OTP verification for high-value transactions and protected operations.

### 6. Merchant Management

- Merchant registration.
- Unique merchant code.
- Business name and business category.
- Merchant wallet.
- Merchant dashboard.
- Merchant transaction history.
- Merchant payment QR code.
- Merchant transaction exports.

### 7. Merchant Payments

- Pay merchants using merchant codes.
- Customer transaction PIN verification.
- Merchant wallet credit.
- Merchant transaction fee of 1%.
- Customer cashback of 2%, capped at ₹50.
- Cashback becomes eligible after 24 hours.

### 8. Refund Management

- Merchant-initiated refunds.
- Seven-day refund period.
- Partial refunds.
- Full refunds.
- Refund amount validation.
- Merchant wallet balance validation.
- Automatic cancellation of pending cashback after a successful refund.

### 9. Money Requests

- Request money using a registered phone number.
- View incoming and outgoing requests.
- Pay money requests.
- Decline requests.
- Cancel requests.
- Automatic expiration after 48 hours.
- Maximum five pending requests for the same payer.

### 10. Bank Accounts and Withdrawals

**Bank Account Management**
- Add bank accounts.
- OTP verification for adding bank accounts.
- IFSC validation.
- Account number validation.
- Maximum three bank accounts per user.
- Primary bank account selection.
- Masked bank account numbers in responses.

**Withdrawals**
- Full KYC requirement for withdrawals.
- Minimum withdrawal amount of ₹100.
- Transaction PIN verification.
- Withdrawal spending-limit validation.
- Withdrawal Clearing ledger account.
- Pending, Completed, and Failed withdrawal statuses.
- Automatic withdrawal processing.
- Simulated bank failure handling and wallet reversal.

### 11. Fraud Detection and Transaction Safety

The transfer service includes the following fraud-detection rules:

- More than five outgoing transfers within one minute.
- A single transfer exceeding ₹20,000.

Suspicious transfers are placed On Hold.

**Admin Fraud Review**
- View flagged transactions.
- Approve held transactions.
- Reject held transactions.
- Release funds to the receiver after approval.
- Return funds to the sender after rejection.
- Record Admin ID, decision reason, and decision timestamp.

### 12. Double-Entry Ledger Accounting

The system uses double-entry accounting.

Every financial transaction contains balanced debit and credit entries.

Example:

| Account | Entry Type | Amount |
|---|---|---:|
| Sender Wallet | Debit | ₹1,000 |
| Receiver Wallet | Credit | ₹1,000 |

System ledger accounts include:

- BANK_SETTLEMENT
- CASHBACK_POOL
- FEES
- WITHDRAWAL_CLEARING
- HOLD

This accounting approach helps maintain transaction consistency and traceability.

### 13. Email Notifications and Scheduled Jobs

The project includes SMTP email configuration and background-processing support.

Planned notification events include:

- Money sent and received.
- Merchant payments and refunds.
- Cashback credited.
- Withdrawal completed or failed.
- Money request received.
- Low wallet balance alerts.
- Transfer held, approved, or rejected.

Scheduled jobs planned for the system:

| Job | Schedule |
|---|---|
| Cashback processing | Hourly |
| Withdrawal processing | Every 5 minutes |
| Money request expiration | Hourly |
| OTP and idempotency cleanup | Daily |
| Wallet and ledger reconciliation | Daily |

*These notification and scheduled-job integrations should be considered complete only after implementation and testing.*

---

## Project Structure

```text
digital_wallet_system/
│
├── app/
│   ├── auth/
│   │   └── security.py
│   │
│   ├── models/
│   │   ├── user.py
│   │   ├── wallet.py
│   │   ├── kyc.py
│   │   ├── otp.py
│   │   ├── bank_account.py
│   │   ├── withdrawal.py
│   │   ├── cashback.py
│   │   ├── money_request.py
│   │   ├── ledger_account.py
│   │   ├── ledger_entry.py
│   │   ├── financial_transaction.py
│   │   ├── fraud_review.py
│   │   └── idempotency.py
│   │
│   ├── schemas/
│   │   ├── auth.py
│   │   ├── wallet.py
│   │   ├── kyc.py
│   │   ├── pin.py
│   │   ├── otp.py
│   │   └── fraud_review.py
│   │
│   ├── routers/
│   │   ├── auth.py
│   │   ├── wallet.py
│   │   ├── kyc.py
│   │   ├── admin.py
│   │   ├── pin.py
│   │   ├── otp.py
│   │   ├── transfers.py
│   │   ├── merchants.py
│   │   ├── payments.py
│   │   ├── refunds.py
│   │   ├── money_requests.py
│   │   ├── bank_accounts.py
│   │   └── withdrawals.py
│   │
│   ├── services/
│   │   ├── ledger_service.py
│   │   ├── transfer_service.py
│   │   ├── merchant_payment_service.py
│   │   ├── merchant_refund_service.py
│   │   ├── money_request_service.py
│   │   ├── withdrawal_service.py
│   │   ├── fraud_review_service.py
│   │   ├── cashback_scheduler.py
│   │   └── email_service.py
│   │
│   ├── database.py
│   └── main.py
│
├── alembic/
│   ├── versions/
│   └── env.py
│
├── statements/
├── tests/
├── .env
├── .env.example
├── .gitignore
├── alembic.ini
├── requirements.txt
└── README.md
```

*The structure above describes the main project modules; your actual directory may contain additional files.*

---

## Installation and Setup

### Prerequisites

Install the following:

- Python 3.9 or later.
- MySQL Server.
- MySQL Workbench (optional).
- Visual Studio Code.
- Git.
- Postman (optional).

### Step 1: Clone the Repository

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
```

Navigate into the project:

```bash
cd digital_wallet_system
```

### Step 2: Create a Virtual Environment

Windows PowerShell:

```powershell
python -m venv .venv
```

Activate the environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

### Step 3: Install Dependencies

```powershell
python -m pip install --upgrade pip
```

```powershell
pip install -r requirements.txt
```

### Step 4: Create MySQL Database

Open MySQL Workbench or MySQL command line.

Execute:

```sql
CREATE DATABASE digital_wallet_db;
```

### Step 5: Configure Environment Variables

Create a `.env` file in the project root.

Example:

```env
APP_NAME=Digital Wallet API
DEBUG=True

DATABASE_URL=mysql+pymysql://root:YOUR_PASSWORD@localhost:3306/digital_wallet_db

SECRET_KEY=YOUR_LONG_RANDOM_SECRET_KEY
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=YOUR_EMAIL@gmail.com
SMTP_PASSWORD=YOUR_EMAIL_APP_PASSWORD

REDIS_URL=redis://localhost:6379/0

STATEMENTS_DIR=statements
```

**Important:**
- Replace `YOUR_PASSWORD` with your MySQL password.
- Replace `YOUR_EMAIL` and `YOUR_EMAIL_APP_PASSWORD` with your SMTP credentials.
- Use an application password where required by your email provider.
- Never upload your actual `.env` file to GitHub.
- If your MySQL password contains special characters, URL-encode them in the database URL.

### Step 6: Run Database Migrations

Generate a migration when new database models or schema changes are introduced:

```powershell
alembic revision --autogenerate -m "initial migration"
```

Review the generated migration and then apply migrations:

```powershell
alembic upgrade head
```

Check migration status:

```powershell
alembic current
```

### Step 7: Start the FastAPI Server

```powershell
uvicorn app.main:app --reload
```

The backend server will run at:

```text
http://127.0.0.1:8000
```

---

## API Documentation

FastAPI automatically generates interactive API documentation.

**Swagger UI:**

http://127.0.0.1:8000/docs

**ReDoc:**

http://127.0.0.1:8000/redoc

**Health Check:**

http://127.0.0.1:8000/health

---

## Important API Endpoints

The following are the main implemented or planned endpoint groups. Check Swagger UI for the exact request fields and available operations.

| Method | Endpoint | Description |
|---|---|---|
| POST | `/auth/register` | Register a user |
| POST | `/auth/login` | Login |
| GET | `/auth/me` | Get logged-in user |
| GET | `/wallet` | Wallet details |
| POST | `/transfers` | Send money |
| GET | `/transfers/{transaction_ref}` | Get transfer details |
| POST | `/payments/merchant` | Pay merchant |
| POST | `/refunds/{transaction_ref}/refund` | Process refund |
| POST | `/money-requests` | Create money request |
| GET | `/money-requests` | View money requests |
| POST | `/bank-accounts` | Add bank account |
| GET | `/bank-accounts` | List bank accounts |
| DELETE | `/bank-accounts/{bank_account_id}` | Delete bank account |
| POST | `/withdrawals` | Create withdrawal |
| GET | `/withdrawals` | View withdrawals |
| GET | `/admin/flagged-transactions` | List flagged transactions |
| PUT | `/admin/transactions/{transaction_ref}/approve` | Approve held transfer |
| PUT | `/admin/transactions/{transaction_ref}/reject` | Reject held transfer |

---

## Security Features

- JWT-based authentication.
- Role-based authorization.
- Password hashing.
- Transaction PIN hashing.
- OTP verification.
- Spending-limit enforcement.
- Wallet status validation.
- Database transactions.
- Row-level locking for important financial operations.
- Double-entry ledger.
- Fraud detection.
- Idempotency support.
- Masked bank account numbers.

**Security note:** This is an educational backend project. It is not a production-ready banking or payment system. Real financial deployment requires additional security audits, regulatory compliance, payment-provider integrations, monitoring, and operational controls.

---

## Testing

Run the API using:

```powershell
uvicorn app.main:app --reload
```

Use Swagger UI or Postman to test:

1. User registration and login.
2. Wallet creation and balance checking.
3. Transaction PIN setup.
4. OTP verification.
5. Money transfers.
6. Merchant registration and payments.
7. Refund processing.
8. Cashback processing.
9. Money requests.
10. Bank account management.
11. Withdrawal processing.
12. Fraud detection and Admin review.
13. KYC approval and wallet freezing.

---

## Future Enhancements

- Integration with real payment gateways.
- Real bank account verification.
- Production-grade transaction monitoring.
- Advanced fraud detection.
- Automated reconciliation reports.
- Docker deployment.
- Cloud hosting.
- CI/CD pipeline.
- Comprehensive automated test coverage.
- Frontend application using React.

---

## Author

**Developed as a Python FastAPI Backend Project**

**Project:** Digital Wallet & Payments System

**Language:** Python

**Framework:** FastAPI

**Database:** MySQL

---

## License

This project is developed for educational and learning purposes. Add an appropriate license before distributing or reusing the project.

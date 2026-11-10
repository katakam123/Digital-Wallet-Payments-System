
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.cashback import Cashback
from app.models.financial_transaction import FinancialTransaction
from app.models.wallet import Wallet
from app.models.ledger_account import LedgerAccount

from app.services.ledger_service import (
    money,
    get_system_account,
    post_transaction,
)


logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone="UTC")


def process_one_cashback(cashback_id: int):
    """
    Process one due cashback record.

    Each cashback is processed in its own database session.
    The cashback status and financial ledger transaction are
    committed together.
    """

    db: Session = SessionLocal()

    try:
        # Lock the cashback row to prevent concurrent crediting.
        cashback = (
            db.query(Cashback)
            .filter(Cashback.id == cashback_id)
            .with_for_update()
            .first()
        )

        if not cashback or cashback.status != "Pending":
            return

        now = datetime.now(timezone.utc)
        available_at = cashback.available_at

        # MySQL may return a naive datetime.
        if available_at.tzinfo is None:
            available_at = available_at.replace(
                tzinfo=timezone.utc
            )

        if now < available_at:
            return

        # Retrieve the original merchant payment.
        original_payment = (
            db.query(FinancialTransaction)
            .filter(
                FinancialTransaction.id
                == cashback.payment_transaction_id
            )
            .first()
        )

        if not original_payment:
            logger.error(
                "Original payment missing for cashback %s",
                cashback.id,
            )
            return

        # Check whether any successful refund exists.
        successful_refund = (
            db.query(FinancialTransaction)
            .filter(
                FinancialTransaction.related_transaction_id
                == original_payment.id,
                FinancialTransaction.type == "Merchant Refund",
                FinancialTransaction.status == "Success",
            )
            .first()
        )

        if original_payment.status in (
            "Partially Refunded",
            "Refunded",
            "Reversed",
        ) or successful_refund:

            cashback.status = "Cancelled"
            db.commit()

            logger.info(
                "Cashback %s cancelled because payment was refunded.",
                cashback.id,
            )
            return

        # Find customer's wallet.
        customer_wallet = (
            db.query(Wallet)
            .filter(
                Wallet.owner_id == cashback.customer_id
            )
            .first()
        )

        if not customer_wallet:
            logger.error(
                "Customer wallet missing for cashback %s",
                cashback.id,
            )
            return

        # Find the customer's wallet ledger account.
        customer_account = (
            db.query(LedgerAccount)
            .filter(
                LedgerAccount.wallet_id == customer_wallet.id,
                LedgerAccount.account_type == "User Wallet",
            )
            .first()
        )

        if not customer_account:
            logger.error(
                "Customer ledger account missing for cashback %s",
                cashback.id,
            )
            return

        # Get Cashback Pool system account.
        cashback_pool = get_system_account(
            db,
            "CASHBACK_POOL",
            lock=False,
        )

        cashback_amount = money(cashback.amount)

        # Debit Cashback Pool and credit customer wallet.
        cashback_transaction = post_transaction(
            db=db,
            initiated_by=cashback.customer_id,
            transaction_type="Cashback Credit",
            amount=cashback_amount,
            postings=[
                (
                    cashback_pool.id,
                    "Debit",
                    cashback_amount,
                ),
                (
                    customer_account.id,
                    "Credit",
                    cashback_amount,
                ),
            ],
            description=(
                f"Cashback for payment "
                f"{original_payment.transaction_ref}"
            ),
            commit=False,
        )

        cashback.status = "Credited"
        cashback.credited_transaction_id = cashback_transaction.id

        # Save the ledger transaction and cashback status together.
        db.commit()

        logger.info(
            "Cashback %s credited successfully. Amount: %s",
            cashback.id,
            cashback_amount,
        )

    except Exception:
        db.rollback()
        logger.exception(
            "Failed to process cashback ID %s",
            cashback_id,
        )

    finally:
        db.close()


def process_pending_cashbacks():
    """
    Find due Pending cashback records and process them.

    The scheduler calls this function every minute.
    """

    db: Session = SessionLocal()

    try:
        now = datetime.now(timezone.utc)

        cashback_ids = [
            row.id
            for row in (
                db.query(Cashback.id)
                .filter(
                    Cashback.status == "Pending",
                    Cashback.available_at <= now,
                )
                .order_by(Cashback.id)
                .limit(100)
                .all()
            )
        ]

    except Exception:
        logger.exception("Could not retrieve pending cashbacks.")
        return

    finally:
        db.close()

    for cashback_id in cashback_ids:
        process_one_cashback(cashback_id)


def start_cashback_scheduler():
    """Start the cashback background scheduler."""

    if not scheduler.running:
        scheduler.add_job(
            process_pending_cashbacks,
            trigger="interval",
            minutes=1,
            id="process_pending_cashbacks",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

        scheduler.start()

        logger.info("Cashback scheduler started.")


def stop_cashback_scheduler():
    """Stop the cashback background scheduler."""

    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Cashback scheduler stopped.")

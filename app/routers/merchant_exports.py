
import csv
from decimal import Decimal
from io import BytesIO, StringIO
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.security import require_user_or_merchant

from app.models.user import User
from app.models.wallet import Wallet
from app.models.ledger_account import LedgerAccount
from app.models.ledger_entry import LedgerEntry
from app.models.financial_transaction import FinancialTransaction


router = APIRouter(
    prefix="/merchants",
    tags=["Merchant Exports"],
)

ZERO = Decimal("0.00")
CENT = Decimal("0.01")

PAYMENT_STATUSES = (
    "Success",
    "Partially Refunded",
    "Refunded",
)


def to_decimal(value):
    if value is None:
        return ZERO

    return Decimal(str(value)).quantize(CENT)


def get_merchant_payment_rows(
    db: Session,
    current_user: User,
):
    """
    Retrieve payment history and refund totals
    belonging only to the authenticated merchant.
    """

    # 1. Validate merchant

    if current_user.role != "Merchant":
        raise HTTPException(
            status_code=403,
            detail="Only merchants can export payment history.",
        )

    if not current_user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Your merchant account is inactive.",
        )

    # 2. Find merchant wallet

    merchant_wallet = (
        db.query(Wallet)
        .filter(
            Wallet.owner_id == current_user.id
        )
        .first()
    )

    if not merchant_wallet:
        raise HTTPException(
            status_code=404,
            detail="Merchant wallet not found.",
        )

    # 3. Find merchant ledger account

    merchant_account = (
        db.query(LedgerAccount)
        .filter(
            LedgerAccount.wallet_id == merchant_wallet.id,
            LedgerAccount.account_type == "Merchant Wallet",
        )
        .first()
    )

    if not merchant_account:
        return []

    # 4. Aggregate successful refunds

    refund_totals = (
        db.query(
            FinancialTransaction.related_transaction_id.label(
                "payment_id"
            ),
            func.sum(
                FinancialTransaction.amount
            ).label("refunded_amount"),
        )
        .filter(
            FinancialTransaction.type == "Merchant Refund",
            FinancialTransaction.status == "Success",
            FinancialTransaction.related_transaction_id.isnot(None),
        )
        .group_by(
            FinancialTransaction.related_transaction_id
        )
        .subquery()
    )

    # 5. Retrieve merchant payments

    rows = (
        db.query(
            FinancialTransaction,
            LedgerEntry.amount.label("merchant_received"),
            User,
            func.coalesce(
                refund_totals.c.refunded_amount,
                0,
            ).label("refunded_amount"),
        )
        .join(
            LedgerEntry,
            LedgerEntry.transaction_id == FinancialTransaction.id,
        )
        .join(
            User,
            User.id == FinancialTransaction.initiated_by,
        )
        .outerjoin(
            refund_totals,
            refund_totals.c.payment_id == FinancialTransaction.id,
        )
        .filter(
            FinancialTransaction.type == "Merchant Payment",
            FinancialTransaction.status.in_(PAYMENT_STATUSES),
            LedgerEntry.account_id == merchant_account.id,
            LedgerEntry.entry_type == "Credit",
        )
        .order_by(
            FinancialTransaction.created_at.desc()
        )
        .all()
    )

    # 6. Prepare export records

    result = []

    for transaction, received, customer, refunded in rows:

        amount = to_decimal(transaction.amount)
        merchant_received = to_decimal(received)
        refunded_amount = to_decimal(refunded)

        merchant_fee = (
            amount - merchant_received
        ).quantize(CENT)

        unrefunded_amount = max(
            ZERO,
            amount - refunded_amount,
        )

        customer_name = (
            getattr(customer, "full_name", None)
            or getattr(customer, "name", None)
            or f"User #{customer.id}"
        )

        result.append({
            "transaction_ref": transaction.transaction_ref,
            "customer_id": customer.id,
            "customer_name": customer_name,
            "amount": amount,
            "merchant_fee": merchant_fee,
            "merchant_received": merchant_received,
            "refunded_amount": refunded_amount,
            "unrefunded_amount": unrefunded_amount,
            "status": transaction.status,
            "created_at": transaction.created_at,
        })

    return result


# ==================================================
# CSV EXPORT
# ==================================================

@router.get("/me/payments/export/csv")
def export_merchant_payments_csv(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_or_merchant),
):
    """
    Download merchant payment history as CSV.
    """

    rows = get_merchant_payment_rows(
        db,
        current_user,
    )

    output = StringIO()

    writer = csv.writer(output)

    writer.writerow([
        "Transaction Reference",
        "Customer ID",
        "Customer Name",
        "Payment Amount (INR)",
        "Merchant Fee (INR)",
        "Merchant Received (INR)",
        "Refunded Amount (INR)",
        "Unrefunded Amount (INR)",
        "Status",
        "Transaction Date",
    ])

    for row in rows:

        writer.writerow([
            row["transaction_ref"],
            row["customer_id"],
            row["customer_name"],
            str(row["amount"]),
            str(row["merchant_fee"]),
            str(row["merchant_received"]),
            str(row["refunded_amount"]),
            str(row["unrefunded_amount"]),
            row["status"],
            row["created_at"].isoformat()
            if row["created_at"]
            else "",
        ])

    # UTF-8 BOM helps Excel display text correctly.
    csv_bytes = (
        "\ufeff" + output.getvalue()
    ).encode("utf-8")

    filename = (
        f"{current_user.merchant_code or 'merchant'}_payments.csv"
    )

    return StreamingResponse(
        iter([csv_bytes]),
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{filename}"'
            )
        },
    )


# ==================================================
# PDF EXPORT
# ==================================================

@router.get("/me/payments/export/pdf")
def export_merchant_payments_pdf(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_or_merchant),
):
    """
    Download merchant payment history as PDF.
    """

    rows = get_merchant_payment_rows(
        db,
        current_user,
    )

    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer,
            Table,
            TableStyle,
        )

    except ImportError:
        raise HTTPException(
            status_code=500,
            detail=(
                "ReportLab is not installed. "
                "Run: pip install reportlab"
            ),
        )

    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=10 * mm,
        leftMargin=10 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title="Merchant Payment Report",
        author="Digital Wallet System",
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        fontSize=17,
        spaceAfter=8,
    )

    normal_style = ParagraphStyle(
        "ReportNormal",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
    )

    small_style = ParagraphStyle(
        "ReportSmall",
        parent=styles["Normal"],
        fontSize=6,
        leading=7,
        alignment=TA_LEFT,
    )

    elements = []

    # Report title

    elements.append(
        Paragraph(
            "Merchant Payment History",
            title_style,
        )
    )

    merchant_name = (
        current_user.business_name
        or current_user.full_name
    )

    elements.append(
        Paragraph(
            f"<b>Merchant:</b> {merchant_name}",
            normal_style,
        )
    )

    elements.append(
        Paragraph(
            f"<b>Merchant Code:</b> "
            f"{current_user.merchant_code or 'N/A'}",
            normal_style,
        )
    )

    elements.append(
        Paragraph(
            "<b>Generated:</b> "
            + datetime.now(timezone.utc).strftime(
                "%Y-%m-%d %H:%M UTC"
            ),
            normal_style,
        )
    )

    elements.append(Spacer(1, 12))

    # Summary calculations

    total_sales = sum(
        (row["amount"] for row in rows),
        ZERO,
    )

    total_fees = sum(
        (row["merchant_fee"] for row in rows),
        ZERO,
    )

    total_received = sum(
        (row["merchant_received"] for row in rows),
        ZERO,
    )

    total_refunds = sum(
        (row["refunded_amount"] for row in rows),
        ZERO,
    )

    net_after_refunds = (
        total_received - total_refunds
    )

    summary = [
        ["Total Payments", str(len(rows))],
        ["Total Sales", f"INR {total_sales:.2f}"],
        ["Total Fees", f"INR {total_fees:.2f}"],
        ["Total Received", f"INR {total_received:.2f}"],
        ["Total Refunds", f"INR {total_refunds:.2f}"],
        ["Net After Refunds", f"INR {net_after_refunds:.2f}"],
    ]

    summary_table = Table(
        summary,
        colWidths=[55 * mm, 45 * mm],
    )

    summary_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.whitesmoke),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("PADDING", (0, 0), (-1, -1), 5),
        ])
    )

    elements.append(summary_table)
    elements.append(Spacer(1, 15))

    # Transaction table

    headers = [
        "Reference",
        "Customer",
        "Amount",
        "Fee",
        "Received",
        "Refunded",
        "Remaining",
        "Status",
        "Date",
    ]

    table_data = [headers]

    for row in rows:

        created_at = row["created_at"]

        date_text = (
            created_at.strftime("%Y-%m-%d %H:%M")
            if created_at
            else ""
        )

        table_data.append([
            Paragraph(
                str(row["transaction_ref"]),
                small_style,
            ),
            Paragraph(
                str(row["customer_name"]),
                small_style,
            ),
            f"{row['amount']:.2f}",
            f"{row['merchant_fee']:.2f}",
            f"{row['merchant_received']:.2f}",
            f"{row['refunded_amount']:.2f}",
            f"{row['unrefunded_amount']:.2f}",
            Paragraph(
                str(row["status"]),
                small_style,
            ),
            Paragraph(
                date_text,
                small_style,
            ),
        ])

    if not rows:
        table_data.append([
            Paragraph(
                "No payment transactions found.",
                small_style,
            ),
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ])

    transaction_table = Table(
        table_data,
        repeatRows=1,
        colWidths=[
            27 * mm,
            28 * mm,
            19 * mm,
            16 * mm,
            19 * mm,
            19 * mm,
            19 * mm,
            25 * mm,
            25 * mm,
        ],
    )

    transaction_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#263B59")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (2, 1), (6, -1), "RIGHT"),
            ("PADDING", (0, 0), (-1, -1), 5),
        ])
    )

    elements.append(transaction_table)

    document.build(elements)

    buffer.seek(0)

    filename = (
        f"{current_user.merchant_code or 'merchant'}_payments.pdf"
    )

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{filename}"'
            )
        },
    )


import smtplib
import logging
import os
import smtplib
from email.message import EmailMessage
from email.message import EmailMessage

from app.database import settings


logger = logging.getLogger(__name__)


def send_login_alert(
    recipient_email: str,
    full_name: str
):

    if not settings.SMTP_USERNAME or not settings.SMTP_PASSWORD:
        logger.warning(
            "Login alert skipped: SMTP credentials are not configured"
        )
        return

    message = EmailMessage()

    message["Subject"] = "Digital Wallet - Login Alert"
    message["From"] = settings.SMTP_USERNAME
    message["To"] = recipient_email

    message.set_content(
        f"""
Hello {full_name},

A successful login to your Digital Wallet account was detected.

If this was you, no action is required.

If you did not perform this login, please contact support immediately.

Thank you,
Digital Wallet Security Team
"""
    )

    try:

        with smtplib.SMTP(
            settings.SMTP_HOST,
            settings.SMTP_PORT,
            timeout=10
        ) as server:

            server.starttls()

            server.login(
                settings.SMTP_USERNAME,
                settings.SMTP_PASSWORD
            )

            server.send_message(message)

    except Exception:

        logger.exception("Failed to send login alert email")
def send_otp_email(to_email: str, otp: str, purpose: str):
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    from_email = os.getenv("SMTP_FROM_EMAIL", smtp_username)

    if not all([smtp_host, smtp_username, smtp_password, from_email]):
        raise RuntimeError("SMTP settings are missing in .env")

    message = EmailMessage()
    message["Subject"] = f"Your Digital Wallet OTP - {purpose}"
    message["From"] = from_email
    message["To"] = to_email

    message.set_content(
        f"""Your Digital Wallet verification OTP is: {otp}

Purpose: {purpose}
This OTP expires in 5 minutes.
Do not share this OTP with anyone.

If you did not request this OTP, please ignore this email.
"""
    )

    with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
        server.starttls()
        server.login(smtp_username, smtp_password)
        server.send_message(message)
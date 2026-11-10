
import logging

from decimal import Decimal

from app.services.websocket_manager import websocket_manager

logger = logging.getLogger(__name__)


async def notify_wallet_event(
    user_id: int,
    event: str,
    balance: Decimal,
    amount: Decimal | None = None,
    transaction_ref: str | None = None,
):
    try:
        await websocket_manager.broadcast_balance_update(
            user_id=user_id,
            balance=str(balance),
            event=event,
            amount=str(amount) if amount is not None else None,
            transaction_ref=transaction_ref,
        )

    except Exception:
        # Notification failures must never affect a completed payment.
        logger.exception(
            "Could not send wallet notification to user %s",
            user_id,
        )

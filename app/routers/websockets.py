
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import jwt, JWTError

from app.database import settings, SessionLocal
from app.models.user import User
from app.services.websocket_manager import websocket_manager

router = APIRouter(tags=["WebSocket Notifications"])

logger = logging.getLogger(__name__)


def get_websocket_user_id(token: str):
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )

        subject = payload.get("sub")

        if not subject:
            return None

        return int(subject)

    except (JWTError, ValueError, TypeError):
        return None


@router.websocket("/ws/notifications")
async def wallet_notifications(websocket: WebSocket, token: str):
    user_id = get_websocket_user_id(token)

    if user_id is None:
        await websocket.close(code=1008)
        return

    db = SessionLocal()

    try:
        user = db.query(User).filter(
            User.id == user_id,
            User.is_active.is_(True),
        ).first()

        if not user:
            await websocket.close(code=1008)
            return

    finally:
        db.close()

    await websocket_manager.connect(user_id, websocket)

    try:
        await websocket.send_json({
            "event": "connected",
            "message": "Wallet notifications connected successfully",
            "user_id": user_id,
        })

        while True:
            # Keep the connection alive.
            # The client can send ping messages.
            data = await websocket.receive_text()

            if data == "ping":
                await websocket.send_json({
                    "event": "pong"
                })

    except WebSocketDisconnect:
        websocket_manager.disconnect(user_id, websocket)

    except Exception:
        logger.exception("WebSocket connection error")
        websocket_manager.disconnect(user_id, websocket)

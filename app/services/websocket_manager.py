
import json
import logging
from collections import defaultdict

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    def __init__(self):
        self.active_connections: dict[int, list[WebSocket]] = defaultdict(list)

    async def connect(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id].append(websocket)

    def disconnect(self, user_id: int, websocket: WebSocket):
        connections = self.active_connections.get(user_id, [])

        if websocket in connections:
            connections.remove(websocket)

        if not connections:
            self.active_connections.pop(user_id, None)

    async def send_to_user(self, user_id: int, message: dict):
        connections = list(self.active_connections.get(user_id, []))

        for websocket in connections:
            try:
                await websocket.send_json(message)
            except Exception:
                logger.exception(
                    "WebSocket delivery failed for user %s", user_id
                )
                self.disconnect(user_id, websocket)

    async def broadcast_balance_update(
        self,
        user_id: int,
        balance: str,
        event: str,
        transaction_ref: str | None = None,
        amount: str | None = None,
    ):
        message = {
            "event": event,
            "user_id": user_id,
            "balance": balance,
            "amount": amount,
            "transaction_ref": transaction_ref,
        }

        await self.send_to_user(user_id, message)


websocket_manager = WebSocketManager()

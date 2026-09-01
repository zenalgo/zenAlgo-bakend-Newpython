import asyncio
import logging
from typing import Dict, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from jose import jwt, JWTError

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.brokers.service import get_user_portfolio_summary

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["WebSockets"])

class ConnectionManager:
    """User-isolated WebSocket connection manager."""
    def __init__(self):
        self.active_connections: Dict[int, Set[WebSocket]] = {}

    async def connect(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)
        logger.info("WebSocket connected for user_id=%s", user_id)

    def disconnect(self, user_id: int, websocket: WebSocket):
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        logger.info("WebSocket disconnected for user_id=%s", user_id)

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        await websocket.send_json(message)

    async def broadcast_to_user(self, user_id: int, message: dict):
        if user_id in self.active_connections:
            for connection in list(self.active_connections[user_id]):
                try:
                    await connection.send_json(message)
                except Exception:
                    self.disconnect(user_id, connection)


manager = ConnectionManager()


@router.websocket("/market")
async def websocket_market_endpoint(websocket: WebSocket, token: str = Query(...)):
    """User-isolated WebSocket stream pushing real-time portfolio snapshots."""
    # Authenticate Platform JWT
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id_str = payload.get("sub")
        if not user_id_str:
            await websocket.close(code=1008)
            return
        user_id = int(user_id_str)
    except (JWTError, ValueError):
        await websocket.close(code=1008)
        return

    await manager.connect(user_id, websocket)

    try:
        while True:
            # Push user-isolated portfolio summary every 1 second
            async with AsyncSessionLocal() as db:
                try:
                    summary = await get_user_portfolio_summary(db, user_id)
                    await manager.send_personal_message(
                        {"type": "PORTFOLIO_SUMMARY", "data": summary},
                        websocket
                    )
                except Exception as ex:
                    await manager.send_personal_message(
                        {"type": "PORTFOLIO_ERROR", "message": str(ex)},
                        websocket
                    )
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)
    except Exception as e:
        logger.error("WebSocket exception for user_id=%s: %s", user_id, str(e))
        manager.disconnect(user_id, websocket)

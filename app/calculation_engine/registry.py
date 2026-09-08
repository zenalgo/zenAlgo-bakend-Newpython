"""
Calculation Engine — Engine Registry & WebSocket Manager
Global in-memory registry holding all active LiveIndicatorEngines and managing
WebSocket client connections for real-time indicator and signal streaming.
"""
from datetime import datetime, timezone
import json
import logging
from typing import Dict, List, Optional, Set, Any
from fastapi import WebSocket

from app.calculation_engine.schemas import LiveEngineStatusItem

logger = logging.getLogger(__name__)

# Forward reference type
_ENGINES: Dict[str, Any] = {}

# Active WebSocket connections: /ws/calc-engine
_WS_CLIENTS: Set[WebSocket] = set()


class CalcEngineRegistry:
    """Singleton registry holding active LiveIndicatorEngines."""

    @staticmethod
    def get(symbol: str) -> Optional[Any]:
        return _ENGINES.get(symbol.strip().upper())

    @staticmethod
    def register(symbol: str, engine: Any) -> None:
        _ENGINES[symbol.strip().upper()] = engine
        logger.info(f"Registered calculation engine for {symbol.upper()}")

    @staticmethod
    def remove(symbol: str) -> Optional[Any]:
        eng = _ENGINES.pop(symbol.strip().upper(), None)
        if eng:
            logger.info(f"Removed calculation engine for {symbol.upper()}")
        return eng

    @staticmethod
    def all() -> Dict[str, Any]:
        return _ENGINES

    @staticmethod
    def get_statuses() -> List[LiveEngineStatusItem]:
        statuses: List[LiveEngineStatusItem] = []
        for sym, eng in _ENGINES.items():
            statuses.append(
                LiveEngineStatusItem(
                    symbol=sym,
                    timeframe=getattr(eng, "timeframe", "5m"),
                    is_running=getattr(eng, "is_running", False),
                    started_at=getattr(eng, "started_at", None),
                    last_snapshot_at=getattr(eng, "last_snapshot_at", None),
                    candle_count=len(getattr(eng, "candles", [])),
                    data_source=getattr(eng, "data_source", "DHAN"),
                    websocket_connected=getattr(eng, "websocket_connected", False),
                    fallback_polling=getattr(eng, "fallback_polling", False),
                )
            )
        return statuses


class CalcEngineWSManager:
    """Manages connected WebSocket subscribers and broadcasts indicator/signal events."""

    @staticmethod
    async def connect(websocket: WebSocket) -> None:
        await websocket.accept()
        _WS_CLIENTS.add(websocket)
        logger.info(f"CalcEngine WebSocket client connected. Total clients: {len(_WS_CLIENTS)}")

    @staticmethod
    def disconnect(websocket: WebSocket) -> None:
        _WS_CLIENTS.discard(websocket)
        logger.info(f"CalcEngine WebSocket client disconnected. Total clients: {len(_WS_CLIENTS)}")

    @staticmethod
    async def broadcast(message: Dict[str, Any]) -> None:
        """Broadcast JSON message to all connected clients."""
        if not _WS_CLIENTS:
            return

        dead_clients = set()
        json_payload = json.dumps(message, default=str)

        for client in list(_WS_CLIENTS):
            try:
                await client.send_text(json_payload)
            except Exception as e:
                logger.debug(f"Error sending to WebSocket client: {e}")
                dead_clients.add(client)

        for dead in dead_clients:
            _WS_CLIENTS.discard(dead)

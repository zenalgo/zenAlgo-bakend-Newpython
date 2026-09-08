"""
Calculation Engine — API Router
REST and WebSocket endpoints for controlling the Live Technical Indicator Engine,
reading real-time indicator snapshots, and streaming live calculation updates and signals.
"""
from datetime import datetime, timezone
import json
import logging
from typing import List, Optional, Dict, Any
import uuid

from fastapi import APIRouter, Depends, Query, Request, HTTPException, status, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, AsyncSessionLocal
from app.core.schemas import ApiResponse
from app.brokers.models import BrokerAccount
from app.instruments.models import Instrument, BrokerInstrument
from app.calculation_engine.schemas import (
    StartEngineRequest,
    IndicatorSnapshot,
    IndicatorValue,
    LiveEngineStatusItem,
    SignalEvent,
)
from app.calculation_engine.engine import LiveIndicatorEngine
from app.calculation_engine.registry import CalcEngineRegistry, CalcEngineWSManager
from app.calculation_engine.data_fetcher import get_candles
from app.calculation_engine.indicators import compute_all_indicators
from app.calculation_engine.condition_evaluator import (
    fetch_active_conditions_for_symbol,
    evaluate_conditions_against_snapshot,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/calc-engine", tags=["Calculation Engine"])


async def resolve_dhan_credentials_and_sec_id(
    db: AsyncSession,
    symbol: str,
    broker_account_id: Optional[int] = None,
    security_id: Optional[str] = None,
    exchange: str = "NSE_EQ",
) -> tuple[Optional[Dict[str, Any]], Optional[str], str]:
    """Helper to locate credentials and broker instrument mapping."""
    credentials = None
    resolved_sec_id = security_id
    resolved_exchange = exchange

    # 1. Resolve credentials
    if broker_account_id:
        stmt = select(BrokerAccount).where(BrokerAccount.id == broker_account_id)
        res = await db.execute(stmt)
        acc = res.scalar_one_or_none()
        if acc:
            credentials = acc.credentials
    else:
        # Pick any active Dhan account
        stmt = (
            select(BrokerAccount)
            .where(BrokerAccount.broker_code == "DHAN", BrokerAccount.status == "ACTIVE")
            .limit(1)
        )
        res = await db.execute(stmt)
        acc = res.scalar_one_or_none()
        if acc:
            credentials = acc.credentials

    # 2. Resolve security ID if not supplied
    if not resolved_sec_id:
        stmt = (
            select(BrokerInstrument.security_id, BrokerInstrument.exchange_segment)
            .join(Instrument, BrokerInstrument.instrument_id == Instrument.id)
            .where(
                Instrument.symbol == symbol.strip().upper(),
                BrokerInstrument.broker_code == "DHAN",
            )
            .limit(1)
        )
        res = await db.execute(stmt)
        row = res.first()
        if row:
            resolved_sec_id = str(row[0])
            resolved_exchange = str(row[1])

    return credentials, resolved_sec_id, resolved_exchange


@router.post("/start", response_model=ApiResponse[Dict[str, Any]])
async def start_indicator_engine(
    body: StartEngineRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Starts or restarts a real-time calculation engine for a symbol.
    Subscribes to Dhan WebSocket / MarketDataService and initiates 5s fallback polling.
    """
    sym = body.symbol.strip().upper()

    # Look up credentials and security_id if not explicitly provided
    creds, sec_id, exch = await resolve_dhan_credentials_and_sec_id(
        db=db,
        symbol=sym,
        broker_account_id=body.broker_account_id,
        security_id=body.security_id,
        exchange=body.exchange,
    )

    # Stop existing instance if already running
    existing = CalcEngineRegistry.get(sym)
    if existing:
        await existing.stop()

    engine = LiveIndicatorEngine(
        symbol=sym,
        timeframe=body.timeframe,
        security_id=sec_id,
        exchange=exch,
        credentials=creds,
    )

    await engine.start()

    snapshot = engine.get_snapshot()
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message=f"Live calculation engine started for {sym} [{body.timeframe}]",
        data={
            "symbol": sym,
            "timeframe": body.timeframe,
            "data_source": engine.data_source,
            "candle_count": len(engine.candles),
            "websocket_connected": engine.websocket_connected,
            "snapshot": snapshot.model_dump(mode="json") if snapshot else None,
        },
        requestId=request_id,
    )


@router.post("/stop/{symbol}", response_model=ApiResponse[Dict[str, Any]])
@router.delete("/stop/{symbol}", response_model=ApiResponse[Dict[str, Any]])
async def stop_indicator_engine(
    symbol: str,
    request: Request,
):
    """Stops the live calculation engine for the given symbol."""
    sym = symbol.strip().upper()
    existing = CalcEngineRegistry.get(sym)
    if existing:
        await existing.stop()
        msg = f"Live calculation engine stopped for {sym}"
    else:
        msg = f"Engine for {sym} was not running"

    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message=msg,
        data={"symbol": sym, "is_running": False},
        requestId=request_id,
    )


@router.get("/status", response_model=ApiResponse[List[LiveEngineStatusItem]])
async def get_engine_statuses(request: Request):
    """Returns the health and operational status of all active engines."""
    statuses = CalcEngineRegistry.get_statuses()
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message=f"{len(statuses)} active calculation engines",
        data=statuses,
        requestId=request_id,
    )


@router.get("/snapshot/{symbol}", response_model=ApiResponse[IndicatorSnapshot])
async def get_indicator_snapshot(
    symbol: str,
    request: Request,
    timeframe: str = Query("5m", description="Candle timeframe: 1m, 5m, 15m, 1h"),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns latest full indicator calculation snapshot for symbol.
    If engine is running, returns live snapshot immediately.
    If not running, computes on-demand from historical candles.
    """
    sym = symbol.strip().upper()
    existing = CalcEngineRegistry.get(sym)
    if existing and existing.snapshot:
        snap = existing.snapshot
    else:
        # Compute on-demand snapshot
        creds, sec_id, exch = await resolve_dhan_credentials_and_sec_id(db=db, symbol=sym)
        candles, src = await get_candles(
            symbol=sym,
            timeframe=timeframe,
            security_id=sec_id,
            exchange_segment=exch,
            credentials=creds,
        )
        snap_dict = compute_all_indicators(
            candles=candles,
            symbol=sym,
            timeframe=timeframe,
            data_source=src,
        )
        ind_objects: List[IndicatorValue] = []
        for raw_ind in snap_dict.get("indicators", []):
            ind_objects.append(IndicatorValue(**raw_ind))

        snap = IndicatorSnapshot(
            symbol=sym,
            timeframe=timeframe,
            timestamp=datetime.now(timezone.utc),
            ltp=snap_dict.get("ltp"),
            vwap=snap_dict.get("vwap"),
            indicators=ind_objects,
            candle_count=snap_dict.get("candle_count", len(candles)),
            is_market_hours=snap_dict.get("is_market_hours", True),
            data_source=src,
        )

    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message=f"Indicator snapshot computed for {sym}",
        data=snap,
        requestId=request_id,
    )


@router.get("/signals", response_model=ApiResponse[List[SignalEvent]])
async def get_recent_signals(request: Request):
    """Returns recent entry/exit signal events across all symbols."""
    all_signals: List[SignalEvent] = []
    for eng in CalcEngineRegistry.all().values():
        all_signals.extend(list(getattr(eng, "recent_signals", [])))

    all_signals.sort(key=lambda s: s.timestamp, reverse=True)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message=f"{len(all_signals)} recent signals retrieved",
        data=all_signals[:50],
        requestId=request_id,
    )


@router.get("/signals/{symbol}", response_model=ApiResponse[List[SignalEvent]])
async def get_symbol_recent_signals(symbol: str, request: Request):
    """Returns recent entry/exit signal events for a specific symbol."""
    all_signals: List[SignalEvent] = []
    eng = CalcEngineRegistry.get(symbol.strip().upper())
    if eng:
        all_signals.extend(list(eng.recent_signals))

    all_signals.sort(key=lambda s: s.timestamp, reverse=True)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message=f"{len(all_signals)} recent signals retrieved for {symbol}",
        data=all_signals[:50],
        requestId=request_id,
    )


@router.get("/conditions/{symbol}", response_model=ApiResponse[List[Dict[str, Any]]])
async def get_strategy_conditions_for_symbol(
    symbol: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Lists all active strategy conditions currently registered for this asset symbol."""
    sym = symbol.strip().upper()
    conds = await fetch_active_conditions_for_symbol(db, sym)
    data = []
    for c, s_id, s_name in conds:
        rule_data = {}
        if c.rule_json:
            try:
                rule_data = json.loads(c.rule_json)
            except Exception:
                pass
        data.append({
            "condition_id": c.id,
            "strategy_id": s_id,
            "strategy_name": s_name,
            "rule_type": c.rule_type,
            "raw_text": c.raw_text,
            "rule_json": rule_data,
        })

    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message=f"Found {len(data)} active strategy conditions for {sym}",
        data=data,
        requestId=request_id,
    )


@router.websocket("/ws")
async def websocket_calc_engine_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint streaming live indicator snapshots, ticks, and condition signal events.
    Connect at: /api/v1/calc-engine/ws
    """
    await CalcEngineWSManager.connect(websocket)
    try:
        while True:
            # Keep-alive / command reception (e.g. ping or symbol subscription)
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        CalcEngineWSManager.disconnect(websocket)
    except Exception as e:
        logger.debug(f"CalcEngine WebSocket error: {e}")
        CalcEngineWSManager.disconnect(websocket)

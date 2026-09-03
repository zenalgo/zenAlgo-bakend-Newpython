from typing import List, Optional, Dict, Any
import uuid
from fastapi import APIRouter, Depends, Query, Request, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.schemas import ApiResponse
from app.core.dependencies import get_current_user
from app.instruments import service
from app.instruments.schemas import (
    InstrumentDTO,
    InstrumentSearchResultDTO,
    SectorSummaryDTO,
    InstrumentQuoteDTO
)

router = APIRouter(prefix="/instruments", tags=["Instruments"])

@router.get("/search", response_model=ApiResponse[List[InstrumentSearchResultDTO]])
async def search_instruments(
    request: Request,
    query: str = Query("", description="Symbol or company name search term"),
    sector: Optional[str] = Query(None, description="Optional sector filter"),
    broker: str = Query("DHAN", description="Broker code for execution mapping"),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Fast autocomplete search for stocks and ETFs with broker-mapped securityId."""
    results = await service.search_instruments(
        db=db,
        query=query,
        sector=sector,
        broker_code=broker,
        limit=limit
    )
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message=f"Found {len(results)} matching instruments",
        data=results,
        requestId=request_id
    )

@router.get("/sectors", response_model=ApiResponse[List[SectorSummaryDTO]])
async def get_sectors(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Returns sector breakdown with instrument counts."""
    sectors = await service.get_sectors(db)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Sectors retrieved successfully",
        data=sectors,
        requestId=request_id
    )

@router.get("", response_model=ApiResponse[List[InstrumentDTO]])
async def list_instruments(
    request: Request,
    sector: Optional[str] = Query(None),
    is_fno: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=250),
    db: AsyncSession = Depends(get_db)
):
    """Paginated list of tradable instruments."""
    items = await service.list_instruments(
        db=db,
        sector=sector,
        is_fno=is_fno,
        skip=skip,
        limit=limit
    )
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Instruments retrieved successfully",
        data=items,
        requestId=request_id
    )

@router.get("/{symbol}/quote", response_model=ApiResponse[InstrumentQuoteDTO])
async def get_instrument_quote(
    symbol: str,
    request: Request,
    broker: str = Query("DHAN", description="Broker code for execution mapping"),
    db: AsyncSession = Depends(get_db)
):
    """Retrieves real-time market price (LTP), day change, and lot size for an instrument."""
    quote = await service.get_stock_quote(db, symbol, broker_code=broker)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    if not quote:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Instrument '{symbol}' not found in Scrip Master"
        )
    return ApiResponse(
        success=True,
        message=f"Live quote for {symbol} retrieved successfully",
        data=quote,
        requestId=request_id
    )

@router.get("/{symbol}", response_model=ApiResponse[InstrumentDTO])
async def get_instrument(
    symbol: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Get single instrument details and broker security ID."""
    inst = await service.get_instrument_by_symbol(db, symbol)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    if not inst:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Instrument '{symbol}' not found"
        )
    return ApiResponse(
        success=True,
        message=f"Instrument '{symbol}' retrieved",
        data=inst,
        requestId=request_id
    )

@router.post("/seed", response_model=ApiResponse[Dict[str, Any]])
async def seed_instruments(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Populates or verifies 210 F&O stocks + ETFs in database."""
    count = await service.seed_instruments_if_empty(db)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message=f"Instruments seed check complete. Total count: {count}",
        data={"totalInstruments": count},
        requestId=request_id
    )

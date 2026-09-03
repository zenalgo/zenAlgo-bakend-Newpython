import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy import select, func, or_, and_, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.instruments.models import Instrument, BrokerInstrument
from app.instruments.schemas import (
    InstrumentDTO,
    BrokerMappingDTO,
    InstrumentSearchResultDTO,
    SectorSummaryDTO,
    InstrumentQuoteDTO
)
from app.instruments.seed_data import INITIAL_INSTRUMENTS

logger = logging.getLogger(__name__)

# In-memory quote cache (symbol -> {data, cached_at})
_STOCK_QUOTE_CACHE: Dict[str, Dict[str, Any]] = {}
STOCK_CACHE_TTL_SECONDS = 30

BASELINE_PRICES: Dict[str, float] = {
    "SUZLON": 46.05,
    "MARUTI": 12850.0,
    "TATAGOLD": 14.82,
    "RELIANCE": 2980.0,
    "HDFCBANK": 1650.0,
    "SBIN": 820.0,
    "TCS": 4200.0,
    "INFY": 1850.0,
    "ITC": 490.0,
    "TATASTEEL": 150.0,
    "ICICIBANK": 1220.0,
    "BHARTIARTL": 1600.0,
    "LT": 3600.0,
    "KOTAKBANK": 1780.0,
    "AXISBANK": 1180.0,
    "TITAN": 3400.0,
    "BAJFINANCE": 6950.0,
    "NTPC": 390.0,
    "ONGC": 290.0,
    "TATAPOWER": 410.0,
    "WIPRO": 520.0,
    "SUNPHARMA": 1800.0,
}

def fetch_stock_quote_sync(symbol: str) -> Dict[str, Any]:
    """Synchronously fetches live stock spot price via yfinance with fast_info."""
    sym_clean = symbol.upper().strip()
    fallback_price = BASELINE_PRICES.get(sym_clean, 100.0)
    try:
        import yfinance as yf
        ticker = yf.Ticker(f"{sym_clean}.NS")
        info = ticker.fast_info
        last_price = float(info.last_price or fallback_price)
        prev_close = float(info.previous_close or last_price)
        day_high = float(info.day_high or last_price * 1.01)
        day_low = float(info.day_low or last_price * 0.99)
        change_pct = ((last_price - prev_close) / prev_close) * 100 if prev_close else 0.0

        return {
            "lastPrice": round(last_price, 2),
            "prevClose": round(prev_close, 2),
            "change": round(last_price - prev_close, 2),
            "changePct": round(change_pct, 2),
            "dayHigh": round(day_high, 2),
            "dayLow": round(day_low, 2),
            "isLive": True
        }
    except Exception as ex:
        logger.warning("Could not fetch yfinance quote for %s: %s. Using baseline.", sym_clean, ex)
        return {
            "lastPrice": round(fallback_price, 2),
            "prevClose": round(fallback_price, 2),
            "change": 0.0,
            "changePct": 0.0,
            "dayHigh": round(fallback_price * 1.01, 2),
            "dayLow": round(fallback_price * 0.99, 2),
            "isLive": False
        }

async def seed_instruments_if_empty(db: AsyncSession) -> int:
    """Seeds default 210 F&O stocks + ETFs if instruments table is empty."""
    count_stmt = select(func.count(Instrument.id))
    res = await db.execute(count_stmt)
    total = res.scalar() or 0
    if total > 0:
        return total

    inserted = 0
    for item in INITIAL_INSTRUMENTS:
        inst = Instrument(
            symbol=item["symbol"],
            company_name=item["company_name"],
            sector=item["sector"],
            instrument_type=item.get("instrument_type", "EQUITY"),
            is_fno=item.get("is_fno", True),
            is_active=True,
        )
        db.add(inst)
        await db.flush()

        dhan_data = item.get("dhan", {})
        broker_inst = BrokerInstrument(
            instrument_id=inst.id,
            broker_code="DHAN",
            security_id=str(dhan_data.get("security_id", "")),
            exchange_segment=dhan_data.get("exchange_segment", "NSE_EQ"),
            trading_symbol=dhan_data.get("trading_symbol", item["symbol"]),
            lot_size=int(dhan_data.get("lot_size", 1)),
            tick_size=float(dhan_data.get("tick_size", 0.05)),
        )
        db.add(broker_inst)
        inserted += 1

    await db.commit()
    return inserted


async def search_instruments(
    db: AsyncSession,
    query: str,
    sector: Optional[str] = None,
    broker_code: str = "DHAN",
    limit: int = 20
) -> List[InstrumentSearchResultDTO]:
    """Fast search across symbols and company names, returning broker-mapped instruments."""
    clean_query = query.strip()
    if not clean_query:
        # Return top 20 popular instruments if query is empty
        stmt = (
            select(Instrument, BrokerInstrument)
            .join(BrokerInstrument, and_(
                BrokerInstrument.instrument_id == Instrument.id,
                BrokerInstrument.broker_code == broker_code
            ))
            .where(Instrument.is_active.is_(True))
            .order_by(Instrument.symbol.asc())
            .limit(limit)
        )
    else:
        # Prioritize exact symbol match, then symbol starts with, then company starts with, then anywhere
        stmt = (
            select(Instrument, BrokerInstrument)
            .join(BrokerInstrument, and_(
                BrokerInstrument.instrument_id == Instrument.id,
                BrokerInstrument.broker_code == broker_code
            ))
            .where(
                Instrument.is_active.is_(True),
                or_(
                    Instrument.symbol.ilike(f"%{clean_query}%"),
                    Instrument.company_name.ilike(f"%{clean_query}%")
                )
            )
        )
        if sector:
            stmt = stmt.where(Instrument.sector == sector)

        # Ordering priority
        stmt = stmt.order_by(
            case(
                (func.upper(Instrument.symbol) == clean_query.upper(), 1),
                (func.upper(Instrument.symbol).startswith(clean_query.upper()), 2),
                (func.upper(Instrument.company_name).startswith(clean_query.upper()), 3),
                else_=4
            ),
            Instrument.symbol.asc()
        ).limit(limit)

    results = await db.execute(stmt)
    rows = results.all()

    output: List[InstrumentSearchResultDTO] = []
    for inst, b_inst in rows:
        sym = inst.symbol.upper()
        cached_info = _STOCK_QUOTE_CACHE.get(sym)
        l_price = cached_info["data"]["lastPrice"] if cached_info else BASELINE_PRICES.get(sym)
        c_pct = cached_info["data"]["changePct"] if cached_info else None

        output.append(
            InstrumentSearchResultDTO(
                symbol=inst.symbol,
                companyName=inst.company_name,
                sector=inst.sector,
                instrumentType=inst.instrument_type,
                securityId=b_inst.security_id,
                exchangeSegment=b_inst.exchange_segment,
                tradingSymbol=b_inst.trading_symbol,
                lotSize=b_inst.lot_size,
                tickSize=float(b_inst.tick_size),
                brokerCode=b_inst.broker_code,
                lastPrice=l_price,
                changePct=c_pct
            )
        )
    return output


async def get_sectors(db: AsyncSession) -> List[SectorSummaryDTO]:
    """Returns list of distinct sectors and the number of instruments in each."""
    stmt = (
        select(Instrument.sector, func.count(Instrument.id).label("count"))
        .where(Instrument.is_active.is_(True))
        .group_by(Instrument.sector)
        .order_by(func.count(Instrument.id).desc())
    )
    res = await db.execute(stmt)
    return [SectorSummaryDTO(sector=row[0], count=row[1]) for row in res.all()]


async def list_instruments(
    db: AsyncSession,
    sector: Optional[str] = None,
    is_fno: Optional[bool] = None,
    skip: int = 0,
    limit: int = 50
) -> List[InstrumentDTO]:
    """Lists instruments with their broker mappings."""
    stmt = (
        select(Instrument)
        .options(selectinload(Instrument.broker_mappings))
        .where(Instrument.is_active.is_(True))
    )
    if sector:
        stmt = stmt.where(Instrument.sector == sector)
    if is_fno is not None:
        stmt = stmt.where(Instrument.is_fno.is_(is_fno))

    stmt = stmt.order_by(Instrument.symbol.asc()).offset(skip).limit(limit)
    res = await db.execute(stmt)
    instruments = res.scalars().all()

    dtos = []
    for inst in instruments:
        mappings = [
            BrokerMappingDTO(
                brokerCode=bm.broker_code,
                securityId=bm.security_id,
                exchangeSegment=bm.exchange_segment,
                tradingSymbol=bm.trading_symbol,
                lotSize=bm.lot_size,
                tickSize=float(bm.tick_size)
            )
            for bm in inst.broker_mappings
        ]
        dtos.append(
            InstrumentDTO(
                id=inst.id,
                symbol=inst.symbol,
                companyName=inst.company_name,
                sector=inst.sector,
                instrumentType=inst.instrument_type,
                isFno=inst.is_fno,
                brokerMappings=mappings
            )
        )
    return dtos


async def get_instrument_by_symbol(db: AsyncSession, symbol: str) -> Optional[InstrumentDTO]:
    """Retrieves an instrument by its symbol."""
    stmt = (
        select(Instrument)
        .options(selectinload(Instrument.broker_mappings))
        .where(func.upper(Instrument.symbol) == symbol.upper().strip())
    )
    res = await db.execute(stmt)
    inst = res.scalar_one_or_none()
    if not inst:
        return None

    mappings = [
        BrokerMappingDTO(
            brokerCode=bm.broker_code,
            securityId=bm.security_id,
            exchangeSegment=bm.exchange_segment,
            tradingSymbol=bm.trading_symbol,
            lotSize=bm.lot_size,
            tickSize=float(bm.tick_size)
        )
        for bm in inst.broker_mappings
    ]
    return InstrumentDTO(
        id=inst.id,
        symbol=inst.symbol,
        companyName=inst.company_name,
        sector=inst.sector,
        instrumentType=inst.instrument_type,
        isFno=inst.is_fno,
        brokerMappings=mappings
    )


async def get_stock_quote(
    db: AsyncSession,
    symbol: str,
    broker_code: str = "DHAN"
) -> Optional[InstrumentQuoteDTO]:
    """Fetches real-time price quote and market details for an instrument."""
    sym_clean = symbol.upper().strip()

    stmt = (
        select(Instrument, BrokerInstrument)
        .join(BrokerInstrument, and_(
            BrokerInstrument.instrument_id == Instrument.id,
            BrokerInstrument.broker_code == broker_code
        ))
        .where(func.upper(Instrument.symbol) == sym_clean)
    )
    res = await db.execute(stmt)
    row = res.first()
    if not row:
        return None
    inst, b_inst = row

    now = datetime.now(timezone.utc).timestamp()
    cached = _STOCK_QUOTE_CACHE.get(sym_clean)
    if cached and (now - cached["cached_at"]) < STOCK_CACHE_TTL_SECONDS:
        quote_data = cached["data"]
    else:
        loop = asyncio.get_running_loop()
        quote_data = await loop.run_in_executor(None, fetch_stock_quote_sync, sym_clean)
        _STOCK_QUOTE_CACHE[sym_clean] = {
            "cached_at": now,
            "data": quote_data
        }

    return InstrumentQuoteDTO(
        symbol=inst.symbol,
        companyName=inst.company_name,
        securityId=b_inst.security_id,
        exchangeSegment=b_inst.exchange_segment,
        lastPrice=quote_data["lastPrice"],
        prevClose=quote_data["prevClose"],
        change=quote_data["change"],
        changePct=quote_data["changePct"],
        dayHigh=quote_data.get("dayHigh"),
        dayLow=quote_data.get("dayLow"),
        lotSize=b_inst.lot_size,
        currency="INR",
        isLive=quote_data.get("isLive", True)
    )

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_instruments_search_tata_gold():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/instruments/search?query=tata+gold")
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        assert len(body["data"]) >= 1
        top_match = body["data"][0]
        assert top_match["symbol"] == "TATAGOLD"
        assert top_match["securityId"] == "21401"
        assert top_match["exchangeSegment"] == "NSE_EQ"
        assert top_match["brokerCode"] == "DHAN"

@pytest.mark.asyncio
async def test_instruments_search_reliance():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/instruments/search?query=reliance")
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        assert len(body["data"]) >= 1
        top_match = body["data"][0]
        assert top_match["symbol"] == "RELIANCE"
        assert top_match["securityId"] == "2885"
        assert top_match["exchangeSegment"] == "NSE_EQ"

@pytest.mark.asyncio
async def test_instruments_sectors_breakdown():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/instruments/sectors")
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        sectors = {s["sector"]: s["count"] for s in body["data"]}
        assert sectors.get("Banking & Financial Services") == 49
        assert sectors.get("Oil, Gas & Energy") == 23
        assert sectors.get("Automobiles & Auto Components") == 14
        assert sectors.get("Information Technology") == 13

@pytest.mark.asyncio
async def test_get_instrument_by_symbol():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/instruments/TATAGOLD")
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        data = body["data"]
        assert data["symbol"] == "TATAGOLD"
        assert data["sector"] == "Commodities & ETFs"
        assert len(data["brokerMappings"]) >= 1
        dhan_mapping = next(m for m in data["brokerMappings"] if m["brokerCode"] == "DHAN")
        assert dhan_mapping["securityId"] == "21401"

@pytest.mark.asyncio
async def test_get_instrument_quote_suzlon():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/instruments/SUZLON/quote")
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        data = body["data"]
        assert data["symbol"] == "SUZLON"
        assert data["securityId"] == "12018"
        assert data["exchangeSegment"] == "NSE_EQ"
        assert data["lastPrice"] > 0
        assert data["lotSize"] == 1
        assert data["currency"] == "INR"

@pytest.mark.asyncio
async def test_get_instrument_quote_tatagold():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/instruments/TATAGOLD/quote")
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        data = body["data"]
        assert data["symbol"] == "TATAGOLD"
        assert data["securityId"] == "21401"
        assert data["lastPrice"] > 0

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from app.brokers.dhan.adapter import DhanAdapter
from app.brokers.base.schemas import OrderRequest
from app.brokers.dhan.exceptions import DhanAPIError, DhanAuthenticationError

@pytest.mark.asyncio
async def test_dhan_adapter_get_form_config():
    adapter = DhanAdapter()
    config = adapter.get_form_config()
    assert config.broker_code == "DHAN"
    assert len(config.fields) == 2

@pytest.mark.asyncio
async def test_dhan_adapter_validate_credentials_sandbox():
    adapter = DhanAdapter()
    creds = {"clientId": "1000000001", "accessToken": "test_token"}
    res = await adapter.validate_credentials(creds)
    assert res.is_valid is True
    assert res.status == "ACTIVE"

@pytest.mark.asyncio
async def test_dhan_adapter_place_order_sandbox():
    adapter = DhanAdapter()
    req = OrderRequest(
        trading_symbol="RELIANCE",
        security_id="2885",
        transaction_type="BUY",
        quantity=10,
        price=Decimal("2500.00")
    )
    res = await adapter.place_order(None, {"clientId": "1000000001", "accessToken": "token"}, req)
    assert res.broker_order_id.startswith("DHAN_MOCK_")
    assert res.order_status == "OPEN"

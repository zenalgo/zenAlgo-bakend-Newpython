import pytest
from app.brokers.registry import broker_registry
from app.brokers.dhan.adapter import DhanAdapter
from app.brokers.mock.adapter import MockBrokerAdapter
from app.core.exceptions import BrokerError

def test_broker_registry_resolution():
    dhan = broker_registry.get("DHAN")
    assert isinstance(dhan, DhanAdapter)
    assert dhan.broker_code == "DHAN"

    mock = broker_registry.get("MOCK")
    assert isinstance(mock, MockBrokerAdapter)
    assert mock.broker_code == "MOCK"

def test_broker_registry_case_insensitivity():
    adapter = broker_registry.get("dhan")
    assert isinstance(adapter, DhanAdapter)

def test_broker_registry_unsupported():
    with pytest.raises(BrokerError) as exc_info:
        broker_registry.get("ZERODHA_NOT_YET_ADDED")
    assert exc_info.value.code == "BROKER_NOT_SUPPORTED"

def test_list_supported_brokers():
    brokers = broker_registry.list_supported_brokers()
    codes = [b.code for b in brokers]
    assert "DHAN" in codes
    assert "MOCK" in codes

def test_get_form_config():
    dhan_cfg = broker_registry.get("DHAN").get_form_config()
    assert dhan_cfg.broker_code == "DHAN"
    assert len(dhan_cfg.fields) >= 2
    field_names = [f.name for f in dhan_cfg.fields]
    assert "clientId" in field_names
    assert "accessToken" in field_names

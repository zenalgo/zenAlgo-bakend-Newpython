from app.brokers.registry import broker_registry
from app.brokers.dhan.adapter import DhanAdapter
from app.brokers.mock.adapter import MockBrokerAdapter

def bootstrap_broker_adapters() -> None:
    """Bootstraps broker adapter registrations into registry.
    Prevents generic broker services from importing concrete broker implementations directly.
    """
    broker_registry.register(DhanAdapter())
    broker_registry.register(MockBrokerAdapter())

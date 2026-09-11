from typing import Dict, List, Type
from app.brokers.base.interface import BrokerAdapter
from app.brokers.base.schemas import BrokerMetadata
from app.core.exceptions import BrokerError

class BrokerRegistry:
    """Central registry and factory for resolving broker adapter implementations."""

    def __init__(self):
        self._adapters: Dict[str, BrokerAdapter] = {}

    def register(self, adapter: BrokerAdapter) -> None:
        """Registers a broker adapter instance."""
        code = adapter.broker_code.upper()
        self._adapters[code] = adapter

    def _ensure_bootstrapped(self) -> None:
        if not self._adapters:
            try:
                from app.brokers.bootstrap import bootstrap_broker_adapters
                bootstrap_broker_adapters()
            except Exception:
                pass

    def get(self, broker_code: str) -> BrokerAdapter:
        """Resolves broker adapter by uppercase code. Raises BROKER_NOT_SUPPORTED if missing."""
        if not broker_code:
            raise BrokerError("Broker code is required", code="BROKER_NOT_SUPPORTED", status_code=400)
        
        self._ensure_bootstrapped()
        code = broker_code.upper()
        adapter = self._adapters.get(code)
        if not adapter:
            raise BrokerError(
                f"Broker '{broker_code}' is not supported",
                code="BROKER_NOT_SUPPORTED",
                status_code=400
            )
        return adapter

    def list_supported_brokers(self) -> List[BrokerMetadata]:
        """Returns metadata list of all registered brokers."""
        self._ensure_bootstrapped()
        result = []
        for code, adapter in self._adapters.items():
            form_cfg = adapter.get_form_config()
            result.append(
                BrokerMetadata(
                    code=code,
                    name=adapter.name,
                    enabled=True,
                    authType=form_cfg.auth_type,
                    connectionType=form_cfg.connection_type
                )
            )
        return result

# Global singleton broker registry instance
broker_registry = BrokerRegistry()

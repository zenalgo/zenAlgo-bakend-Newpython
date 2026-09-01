from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

from app.brokers.base.schemas import (
    OrderRequest,
    OrderResult,
    OrderStatus,
    Position,
    Holding,
    Funds,
    BrokerProfile,
    BrokerFormConfig,
    ValidationResult
)

class BrokerAdapter(ABC):
    """Abstract Base Class defining standard interface for all broker integrations."""

    @property
    @abstractmethod
    def broker_code(self) -> str:
        """Returns uppercase unique code for broker (e.g. 'DHAN', 'ZERODHA')."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Returns display name for broker."""
        pass

    @abstractmethod
    def get_form_config(self) -> BrokerFormConfig:
        """Returns dynamic connection form field metadata for frontend UI rendering."""
        pass

    @abstractmethod
    async def validate_credentials(self, credentials: Dict[str, Any]) -> ValidationResult:
        """Validates raw connection credentials supplied by user."""
        pass

    @abstractmethod
    async def validate_connection(self, account: Any, credentials: Dict[str, Any]) -> ValidationResult:
        """Validates whether an existing stored account session is active and valid."""
        pass

    @abstractmethod
    async def get_profile(self, account: Any, credentials: Dict[str, Any]) -> BrokerProfile:
        """Retrieves profile info from broker API."""
        pass

    @abstractmethod
    async def place_order(self, account: Any, credentials: Dict[str, Any], order_req: OrderRequest) -> OrderResult:
        """Places market or limit order with broker."""
        pass

    @abstractmethod
    async def cancel_order(self, account: Any, credentials: Dict[str, Any], order_id: str) -> bool:
        """Cancels open order."""
        pass

    @abstractmethod
    async def modify_order(self, account: Any, credentials: Dict[str, Any], order_id: str, order_req: OrderRequest) -> OrderResult:
        """Modifies existing open order."""
        pass

    @abstractmethod
    async def get_order_status(self, account: Any, credentials: Dict[str, Any], order_id: str) -> OrderStatus:
        """Checks status of order."""
        pass

    @abstractmethod
    async def get_positions(self, account: Any, credentials: Dict[str, Any]) -> List[Position]:
        """Retrieves user net and intraday positions."""
        pass

    @abstractmethod
    async def get_holdings(self, account: Any, credentials: Dict[str, Any]) -> List[Holding]:
        """Retrieves user demat holdings."""
        pass

    @abstractmethod
    async def get_funds(self, account: Any, credentials: Dict[str, Any]) -> Funds:
        """Retrieves fund / margin limit details."""
        pass

    # Optional Extended Operations
    async def calculate_margin(self, account: Any, credentials: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
        """Calculates margin requirement for order contract."""
        return {"status": "SUCCESS", "totalMarginRequired": 0.0}

    async def convert_position(self, account: Any, credentials: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
        """Converts position product type."""
        return {"status": "SUCCESS", "message": "Position converted"}

    async def get_trades(self, account: Any, credentials: Dict[str, Any], order_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieves trade execution history."""
        return []

    async def get_forever_orders(self, account: Any, credentials: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Retrieves GTT forever orders."""
        return []

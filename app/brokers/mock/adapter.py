import uuid
from typing import List, Dict, Any
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from app.brokers.base.interface import BrokerAdapter
from app.brokers.base.schemas import (
    OrderRequest,
    OrderResult,
    OrderStatus,
    Position,
    Holding,
    Funds,
    BrokerProfile,
    BrokerFormConfig,
    FormField,
    ValidationResult
)

class MockBrokerAdapter(BrokerAdapter):
    """Mock broker adapter implementation for unit testing and offline execution without Dhan."""

    @property
    def broker_code(self) -> str:
        return "MOCK"

    @property
    def name(self) -> str:
        return "Mock Test Broker"

    def get_form_config(self) -> BrokerFormConfig:
        return BrokerFormConfig(
            brokerCode="MOCK",
            name="Mock Test Broker",
            authType="TOKEN",
            connectionType="TOKEN",
            fields=[
                FormField(name="clientId", label="Client ID", type="text", required=True, placeholder="Enter Mock Client ID"),
                FormField(name="accessToken", label="Access Token", type="password", required=True, placeholder="Enter Mock Access Token")
            ]
        )

    async def validate_credentials(self, credentials: Dict[str, Any]) -> ValidationResult:
        client_id = credentials.get("clientId")
        access_token = credentials.get("accessToken")
        if not client_id or not access_token:
            return ValidationResult(is_valid=False, status="INVALID", message="Missing clientId or accessToken")
        
        now = datetime.now(timezone.utc)
        return ValidationResult(
            is_valid=True,
            status="ACTIVE",
            message="Mock credentials validated",
            expiry_time=now + timedelta(days=30)
        )

    async def validate_connection(self, account: Any, credentials: Dict[str, Any]) -> ValidationResult:
        if account.status.upper() != "ACTIVE":
            return ValidationResult(is_valid=False, status=account.status, message=f"Session status is {account.status}")
        
        now = datetime.now(timezone.utc)
        if account.expiry_time and account.expiry_time.astimezone(timezone.utc) < now:
            return ValidationResult(is_valid=False, status="EXPIRED", message=f"Session expired at {account.expiry_time}")
            
        return ValidationResult(is_valid=True, status="ACTIVE", message="Mock session active")

    async def get_profile(self, account: Any, credentials: Dict[str, Any]) -> BrokerProfile:
        client_id = account.account_client_id if account else credentials.get("clientId", "MOCK_CLIENT_001")
        return BrokerProfile(
            client_id=client_id,
            name="Mocked Test User",
            ucc="MOCKUCC123",
            email="mock_user@example.com",
            mobile_no="9999999999"
        )

    async def place_order(self, account: Any, credentials: Dict[str, Any], order_req: OrderRequest) -> OrderResult:
        order_id = f"MOCK_ORD_{str(uuid.uuid4())[:8]}"
        return OrderResult(
            broker_order_id=order_id,
            order_status="SUCCESS",
            message="Mock order placed successfully",
            raw_response={"orderId": order_id, "status": "SUCCESS"}
        )

    async def cancel_order(self, account: Any, credentials: Dict[str, Any], order_id: str) -> bool:
        return True

    async def modify_order(self, account: Any, credentials: Dict[str, Any], order_id: str, order_req: OrderRequest) -> OrderResult:
        return OrderResult(
            broker_order_id=order_id,
            order_status="SUCCESS",
            message="Mock order modified successfully"
        )

    async def get_order_status(self, account: Any, credentials: Dict[str, Any], order_id: str) -> OrderStatus:
        return OrderStatus(
            broker_order_id=order_id,
            status="FILLED",
            filled_quantity=100,
            avg_price=Decimal("150.00")
        )

    async def get_positions(self, account: Any, credentials: Dict[str, Any]) -> List[Position]:
        return [
            Position(
                trading_symbol="NIFTY26AUG25000CE",
                security_id="14321",
                position_type="INTRADAY",
                exchange_segment="NSE_FN",
                product_type="MIS",
                net_qty=50,
                buy_qty=50,
                sell_qty=0,
                buy_avg=Decimal("120.00"),
                sell_avg=Decimal("0.00"),
                realized_profit=Decimal("0.00"),
                unrealized_profit=Decimal("500.00")
            )
        ]

    async def get_holdings(self, account: Any, credentials: Dict[str, Any]) -> List[Holding]:
        return [
            Holding(
                trading_symbol="RELIANCE",
                security_id="2885",
                isin="INE002A01018",
                exchange="NSE",
                total_qty=10,
                available_qty=10,
                avg_cost_price=Decimal("2500.00"),
                last_traded_price=Decimal("2600.00")
            )
        ]

    async def get_funds(self, account: Any, credentials: Dict[str, Any]) -> Funds:
        return Funds(
            available_balance=Decimal("100000.00"),
            sod_limit=Decimal("100000.00"),
            collateral_amount=Decimal("0.00"),
            receiveable_amount=Decimal("0.00"),
            utilized_amount=Decimal("10000.00"),
            blocked_payout_amount=Decimal("0.00"),
            withdrawable_balance=Decimal("90000.00")
        )

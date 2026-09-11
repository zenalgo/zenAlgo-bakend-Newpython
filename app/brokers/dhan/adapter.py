import uuid
import logging
from typing import List, Dict, Any, Optional
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
from app.brokers.dhan.http_client import dhan_http_client
from app.brokers.dhan.exceptions import DhanAPIError, DhanAuthenticationError
from app.core.config import settings
from app.core.exceptions import ValidationError, BrokerError

logger = logging.getLogger(__name__)

class DhanAdapter(BrokerAdapter):
    """Dhan HQ broker adapter encapsulating all Dhan API v2 communication and schema mappings."""

    @property
    def broker_code(self) -> str:
        return "DHAN"

    @property
    def name(self) -> str:
        return "Dhan HQ"

    def get_form_config(self) -> BrokerFormConfig:
        return BrokerFormConfig(
            brokerCode="DHAN",
            name="Dhan HQ",
            authType="TOKEN",
            connectionType="TOKEN",
            fields=[
                FormField(
                    name="clientId",
                    label="Client ID",
                    type="text",
                    required=True,
                    placeholder="Enter your Dhan Client ID (e.g. 1000000001)"
                ),
                FormField(
                    name="accessToken",
                    label="Access Token",
                    type="password",
                    required=True,
                    placeholder="Enter Dhan Access Token"
                )
            ]
        )

    async def validate_credentials(self, credentials: Dict[str, Any]) -> ValidationResult:
        client_id = credentials.get("clientId") or credentials.get("client_id")
        access_token = credentials.get("accessToken") or credentials.get("access_token")

        if not client_id or not access_token:
            return ValidationResult(
                is_valid=False,
                status="INVALID",
                message="Both clientId and accessToken are required for Dhan connection"
            )

        if settings.DHAN_SANDBOX_MODE:
            now = datetime.now(timezone.utc)
            expiry = credentials.get("expiryTime") or (now + timedelta(days=30))
            return ValidationResult(
                is_valid=True,
                status="ACTIVE",
                message="Dhan sandbox token validated successfully",
                expiry_time=expiry
            )

        try:
            res_data = await dhan_http_client._request(
                method="GET",
                path="/v2/profile",
                credentials={"clientId": client_id, "accessToken": access_token}
            )
            now = datetime.now(timezone.utc)
            expiry = credentials.get("expiryTime") or (now + timedelta(days=30))
            return ValidationResult(
                is_valid=True,
                status="ACTIVE",
                message="Dhan connection validated",
                expiry_time=expiry
            )
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                status="INVALID",
                message=f"Failed to connect to Dhan API: {str(e)}"
            )

    async def validate_connection(self, account: Any, credentials: Dict[str, Any]) -> ValidationResult:
        if not account or account.status.upper() != "ACTIVE":
            status = account.status if account else "NOT_FOUND"
            return ValidationResult(
                is_valid=False,
                status="INVALID",
                message=f"Dhan session status is {status}"
            )

        now = datetime.now(timezone.utc)
        if account.expiry_time and account.expiry_time.astimezone(timezone.utc) < now:
            return ValidationResult(
                is_valid=False,
                status="EXPIRED",
                message=f"Dhan session expired at {account.expiry_time}"
            )

        return ValidationResult(
            is_valid=True,
            status="ACTIVE",
            message="Dhan session is active and valid"
        )

    async def get_profile(self, account: Any, credentials: Dict[str, Any]) -> BrokerProfile:
        client_id = credentials.get("clientId") or (account.account_client_id if account else "")

        if settings.DHAN_SANDBOX_MODE:
            return BrokerProfile(
                client_id=client_id,
                name="Mocked Dhan Trader",
                ucc="MOCK12345",
                email="mocked_trader@dhan.co",
                mobile_no="9876543210"
            )

        data = await dhan_http_client._request(
            method="GET",
            path="/v2/profile",
            credentials=credentials
        )
        return BrokerProfile(
            client_id=client_id,
            name=data.get("dhanClientName") or data.get("name") or f"Dhan Trader ({client_id})",
            ucc=data.get("dhanClientUcc") or (f"Segments: {data.get('activeSegment').strip(', ')}" if data.get("activeSegment") else ""),
            email=data.get("email") or "",
            mobile_no=data.get("mobileNo") or data.get("mobile") or (f"Valid: {data.get('tokenValidity')}" if data.get("tokenValidity") else "")
        )

    async def get_funds(self, account: Any, credentials: Dict[str, Any]) -> Funds:
        if settings.DHAN_SANDBOX_MODE:
            return Funds(
                available_balance=Decimal("100000.00"),
                sod_limit=Decimal("100000.00"),
                collateral_amount=Decimal("0.00"),
                utilized_amount=Decimal("0.00"),
                withdrawable_balance=Decimal("100000.00")
            )

        data = await dhan_http_client._request(
            method="GET",
            path="/v2/fundlimit",
            credentials=credentials
        )
        return Funds(
            available_balance=Decimal(str(data.get("availabelBalance") or data.get("availableBalance") or 0)),
            sod_limit=Decimal(str(data.get("sodLimit") or 0)),
            collateral_amount=Decimal(str(data.get("collateralAmount") or 0)),
            utilized_amount=Decimal(str(data.get("utilizedAmount") or 0)),
            withdrawable_balance=Decimal(str(data.get("withdrawableBalance") or 0))
        )

    async def get_holdings(self, account: Any, credentials: Dict[str, Any]) -> List[Holding]:
        if settings.DHAN_SANDBOX_MODE:
            return [
                Holding(
                    trading_symbol="RELIANCE",
                    security_id="2885",
                    isin="INE002A01018",
                    total_qty=50,
                    available_qty=50,
                    avg_cost_price=Decimal("2450.00"),
                    last_traded_price=Decimal("2510.00")
                )
            ]

        data_list = await dhan_http_client._request(
            method="GET",
            path="/v2/holdings",
            credentials=credentials
        )
        res = []
        if isinstance(data_list, list):
            for h in data_list:
                res.append(
                    Holding(
                        trading_symbol=h.get("tradingSymbol", ""),
                        security_id=str(h.get("securityId", "")),
                        isin=h.get("isin", ""),
                        total_qty=int(h.get("totalQty", 0)),
                        available_qty=int(h.get("availableQty", 0)),
                        avg_cost_price=Decimal(str(h.get("avgCostPrice") or 0)),
                        last_traded_price=Decimal(str(h.get("lastTradedPrice") or 0))
                    )
                )
        return res

    async def get_positions(self, account: Any, credentials: Dict[str, Any]) -> List[Position]:
        if settings.DHAN_SANDBOX_MODE:
            return [
                Position(
                    trading_symbol="BANKNIFTY-MAR-FUT",
                    security_id="35001",
                    position_type="INTRADAY",
                    net_qty=15,
                    buy_qty=15,
                    sell_qty=0,
                    buy_avg=Decimal("48000.00"),
                    sell_avg=Decimal("0.00"),
                    realized_profit=Decimal("0.00"),
                    unrealized_profit=Decimal("1250.00")
                )
            ]

        data_list = await dhan_http_client._request(
            method="GET",
            path="/v2/positions",
            credentials=credentials
        )
        res = []
        if isinstance(data_list, list):
            for p in data_list:
                res.append(
                    Position(
                        trading_symbol=p.get("tradingSymbol", ""),
                        security_id=str(p.get("securityId", "")),
                        position_type=p.get("positionType", "INTRADAY"),
                        net_qty=int(p.get("netQty", 0)),
                        buy_qty=int(p.get("buyQty", 0)),
                        sell_qty=int(p.get("sellQty", 0)),
                        buy_avg=Decimal(str(p.get("buyAvg") or 0)),
                        sell_avg=Decimal(str(p.get("sellAvg") or 0)),
                        realized_profit=Decimal(str(p.get("realizedProfit") or 0)),
                        unrealized_profit=Decimal(str(p.get("unrealizedProfit") or 0))
                    )
                )
        return res

    async def place_order(self, account: Any, credentials: Dict[str, Any], order_req: OrderRequest) -> OrderResult:
        client_id = credentials.get("clientId") or (account.account_client_id if account else "")

        if settings.DHAN_SANDBOX_MODE:
            order_id = f"DHAN_MOCK_{str(uuid.uuid4())[:8]}"
            return OrderResult(
                broker_order_id=order_id,
                order_status="OPEN",
                message="Order submitted to Dhan in sandbox mode",
                raw_response={"orderId": order_id, "orderStatus": "OPEN"}
            )

        exchange_segment = (order_req.exchange_segment or "NSE_EQ").upper()
        if exchange_segment in ["NSE_FN", "FNO", "NFO"]:
            exchange_segment = "NSE_FNO"
        elif exchange_segment in ["NSE", "EQ"]:
            exchange_segment = "NSE_EQ"

        product_type = (order_req.product_type or "INTRADAY").upper()
        if product_type in ["MIS", "INTRADAY"]:
            product_type = "INTRADAY"
        elif product_type in ["NRML", "MARGIN"]:
            product_type = "MARGIN"
        elif product_type in ["CNC", "DELIVERY"]:
            product_type = "CNC"

        order_type = (order_req.order_type or "MARKET").upper()
        price = float(order_req.price or 0.0)
        if order_type == "MARKET":
            price = 0.0

        payload = {
            "dhanClientId": client_id,
            "correlationId": (order_req.correlation_id or f"CID-{str(uuid.uuid4())[:12]}")[:25],
            "transactionType": order_req.transaction_type.upper(),
            "exchangeSegment": exchange_segment,
            "productType": product_type,
            "orderType": order_type,
            "validity": order_req.validity or "DAY",
            "securityId": str(order_req.security_id),
            "quantity": int(order_req.quantity),
            "price": price,
        }

        # Include triggerPrice for SL order types
        if order_type in ("STOP_LOSS", "STOP_LOSS_MARKET"):
            payload["triggerPrice"] = float(order_req.trigger_price or 0.0)

        data = await dhan_http_client._request(
            method="POST",
            path="/v2/orders",
            credentials=credentials,
            payload=payload
        )
        
        order_id = data.get("orderId") or data.get("dhanOrderId") or str(uuid.uuid4())
        dhan_status = str(data.get("orderStatus", "PENDING")).upper()
        
        status_map = {
            "SUCCESS": "OPEN",
            "TRANSIT": "PENDING",
            "PENDING": "PENDING",
            "REJECTED": "REJECTED",
            "CANCELLED": "CANCELLED",
            "TRADED": "FILLED"
        }
        mapped_status = status_map.get(dhan_status, "PENDING")

        return OrderResult(
            broker_order_id=str(order_id),
            order_status=mapped_status,
            raw_response=data
        )

    async def cancel_order(self, account: Any, credentials: Dict[str, Any], order_id: str) -> bool:
        if settings.DHAN_SANDBOX_MODE:
            return True

        await dhan_http_client._request(
            method="DELETE",
            path=f"/v2/orders/{order_id}",
            credentials=credentials
        )
        return True

    async def modify_order(self, account: Any, credentials: Dict[str, Any], order_id: str, order_req: OrderRequest) -> OrderResult:
        if settings.DHAN_SANDBOX_MODE:
            return OrderResult(broker_order_id=order_id, order_status="OPEN")

        payload = {
            "dhanClientId": credentials.get("clientId"),
            "orderId": order_id,
            "orderType": order_req.order_type,
            "quantity": int(order_req.quantity),
            "price": float(order_req.price)
        }
        data = await dhan_http_client._request(
            method="PUT",
            path=f"/v2/orders/{order_id}",
            credentials=credentials,
            payload=payload
        )
        return OrderResult(broker_order_id=order_id, order_status="OPEN", raw_response=data)

    async def get_order_status(self, account: Any, credentials: Dict[str, Any], order_id: str) -> OrderStatus:
        if settings.DHAN_SANDBOX_MODE:
            return OrderStatus(broker_order_id=order_id, status="FILLED", filled_quantity=100)

        data = await dhan_http_client._request(
            method="GET",
            path=f"/v2/orders/{order_id}",
            credentials=credentials
        )
        dhan_status = str(data.get("orderStatus", "PENDING")).upper()
        status_map = {
            "SUCCESS": "OPEN",
            "TRANSIT": "PENDING",
            "PENDING": "PENDING",
            "REJECTED": "REJECTED",
            "CANCELLED": "CANCELLED",
            "TRADED": "FILLED"
        }
        mapped_status = status_map.get(dhan_status, "PENDING")

        return OrderStatus(
            broker_order_id=order_id,
            status=mapped_status,
            filled_quantity=int(data.get("tradedQuantity") or data.get("quantity") or 0)
        )

    async def calculate_margin(self, account: Any, credentials: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
        if settings.DHAN_SANDBOX_MODE:
            return {"status": "SUCCESS", "totalMarginRequired": 45250.00}

        return await dhan_http_client._request(
            method="POST",
            path="/v2/margincalculator",
            credentials=credentials,
            payload=payload
        )

    async def convert_position(self, account: Any, credentials: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
        if settings.DHAN_SANDBOX_MODE:
            return {"status": "SUCCESS", "message": "Position converted"}

        return await dhan_http_client._request(
            method="POST",
            path="/v2/positions/convert",
            credentials=credentials,
            payload=payload
        )

    async def get_orders(self, account: Any, credentials: Dict[str, Any]) -> List[Dict[str, Any]]:
        if settings.DHAN_SANDBOX_MODE:
            return [
                {
                    "orderId": "DHAN_MOCK_101",
                    "tradingSymbol": "NIFTY 24500 CE",
                    "securityId": "52145",
                    "transactionType": "BUY",
                    "exchangeSegment": "NSE_FNO",
                    "productType": "INTRADAY",
                    "orderType": "MARKET",
                    "orderStatus": "TRADED",
                    "quantity": 50,
                    "price": 142.50,
                    "createTime": "2026-09-03T09:20:15Z"
                },
                {
                    "orderId": "DHAN_MOCK_102",
                    "tradingSymbol": "BANKNIFTY 52000 PE",
                    "securityId": "53890",
                    "transactionType": "SELL",
                    "exchangeSegment": "NSE_FNO",
                    "productType": "INTRADAY",
                    "orderType": "LIMIT",
                    "orderStatus": "OPEN",
                    "quantity": 15,
                    "price": 285.00,
                    "createTime": "2026-09-03T10:15:30Z"
                }
            ]

        res = await dhan_http_client._request(
            method="GET",
            path="/v2/orders",
            credentials=credentials
        )
        return res if isinstance(res, list) else []

    async def get_trades(self, account: Any, credentials: Dict[str, Any], order_id: Optional[str] = None) -> List[Dict[str, Any]]:
        path = f"/v2/trades/{order_id}" if order_id else "/v2/trades"
        if settings.DHAN_SANDBOX_MODE:
            return [
                {
                    "tradeId": "TRD_MOCK_901",
                    "orderId": "DHAN_MOCK_101",
                    "tradingSymbol": "NIFTY 24500 CE",
                    "transactionType": "BUY",
                    "exchangeSegment": "NSE_FNO",
                    "productType": "INTRADAY",
                    "tradedQuantity": 50,
                    "tradedPrice": 142.50,
                    "tradeTime": "2026-09-03T09:20:18Z"
                }
            ]

        res = await dhan_http_client._request(
            method="GET",
            path=path,
            credentials=credentials
        )
        return res if isinstance(res, list) else []

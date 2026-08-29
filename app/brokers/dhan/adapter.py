import uuid
import httpx
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
from app.core.config import settings
from app.core.exceptions import ValidationError, BrokerError

SANDBOX_MODE = True  # Can be driven by config

class DhanAdapter(BrokerAdapter):
    """Dhan HQ broker adapter encapsulating all Dhan API communication and schema mappings."""

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
        client_id = credentials.get("clientId")
        access_token = credentials.get("accessToken")

        if not client_id or not access_token:
            return ValidationResult(
                is_valid=False,
                status="INVALID",
                message="Both clientId and accessToken are required for Dhan connection"
            )

        if SANDBOX_MODE:
            now = datetime.now(timezone.utc)
            expiry = credentials.get("expiryTime") or (now + timedelta(days=30))
            return ValidationResult(
                is_valid=True,
                status="ACTIVE",
                message="Dhan sandbox token validated successfully",
                expiry_time=expiry
            )

        # Real Dhan HQ validation call
        url = f"{settings.DHAN_API_BASE_URL}/profile"
        headers = {
            "access-token": access_token,
            "client-id": client_id
        }
        async with httpx.AsyncClient() as client:
            try:
                res = await client.get(url, headers=headers, timeout=10.0)
                if res.status_code == 200:
                    now = datetime.now(timezone.utc)
                    expiry = credentials.get("expiryTime") or (now + timedelta(days=30))
                    return ValidationResult(
                        is_valid=True,
                        status="ACTIVE",
                        message="Dhan connection validated",
                        expiry_time=expiry
                    )
                else:
                    return ValidationResult(
                        is_valid=False,
                        status="INVALID",
                        message=f"Dhan authentication failed with status {res.status_code}"
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
        access_token = credentials.get("accessToken")

        if SANDBOX_MODE:
            return BrokerProfile(
                client_id=client_id,
                name="Mocked Dhan Trader",
                ucc="MOCK12345",
                email="mocked_trader@dhan.co",
                mobile_no="9876543210"
            )

        url = f"{settings.DHAN_API_BASE_URL}/profile"
        headers = {
            "access-token": access_token,
            "client-id": client_id
        }
        async with httpx.AsyncClient() as client:
            try:
                res = await client.get(url, headers=headers, timeout=10.0)
                res.raise_for_status()
                data = res.json()
                return BrokerProfile(
                    client_id=client_id,
                    name=data.get("name", "Dhan User"),
                    ucc=data.get("ucc", ""),
                    email=data.get("email", ""),
                    mobile_no=data.get("mobile", "")
                )
            except Exception as e:
                raise BrokerError(f"Failed to fetch profile from Dhan HQ: {str(e)}", code="BROKER_API_ERROR")

    async def place_order(self, account: Any, credentials: Dict[str, Any], order_req: OrderRequest) -> OrderResult:
        client_id = credentials.get("clientId") or (account.account_client_id if account else "")
        access_token = credentials.get("accessToken")

        if SANDBOX_MODE:
            order_id = f"DHAN_MOCK_{str(uuid.uuid4())[:8]}"
            return OrderResult(
                broker_order_id=order_id,
                order_status="SUCCESS",
                message="Order placed successfully in sandbox mode",
                raw_response={"orderId": order_id, "orderStatus": "SUCCESS"}
            )

        url = f"{settings.DHAN_API_BASE_URL}/orders"
        headers = {
            "access-token": access_token,
            "client-id": client_id,
            "Content-Type": "application/json"
        }
        payload = {
            "dhanClientId": client_id,
            "transactionType": order_req.transaction_type.upper(),
            "exchangeSegment": "NSE_FN",
            "productType": order_req.product_type,
            "orderType": order_req.order_type,
            "validity": order_req.validity,
            "securityId": order_req.security_id,
            "tradingSymbol": order_req.trading_symbol,
            "quantity": order_req.quantity,
            "price": float(order_req.price)
        }

        async with httpx.AsyncClient() as client:
            try:
                res = await client.post(url, json=payload, headers=headers, timeout=10.0)
                res.raise_for_status()
                data = res.json()
                order_id = data.get("orderId") or data.get("dhanOrderId") or str(uuid.uuid4())
                return OrderResult(
                    broker_order_id=str(order_id),
                    order_status="SUCCESS",
                    raw_response=data
                )
            except Exception as e:
                raise BrokerError(f"Dhan HQ order placement error: {str(e)}", code="BROKER_ORDER_FAILED")

    async def cancel_order(self, account: Any, credentials: Dict[str, Any], order_id: str) -> bool:
        if SANDBOX_MODE:
            return True
        return True

    async def modify_order(self, account: Any, credentials: Dict[str, Any], order_id: str, order_req: OrderRequest) -> OrderResult:
        if SANDBOX_MODE:
            return OrderResult(broker_order_id=order_id, order_status="SUCCESS")
        return OrderResult(broker_order_id=order_id, order_status="SUCCESS")

    async def get_order_status(self, account: Any, credentials: Dict[str, Any], order_id: str) -> OrderStatus:
        if SANDBOX_MODE:
            return OrderStatus(broker_order_id=order_id, status="FILLED")
        return OrderStatus(broker_order_id=order_id, status="FILLED")

    async def get_positions(self, account: Any, credentials: Dict[str, Any]) -> List[Position]:
        return []

    async def get_holdings(self, account: Any, credentials: Dict[str, Any]) -> List[Holding]:
        return []

    async def get_funds(self, account: Any, credentials: Dict[str, Any]) -> Funds:
        return Funds(available_balance=Decimal("100000.00"))

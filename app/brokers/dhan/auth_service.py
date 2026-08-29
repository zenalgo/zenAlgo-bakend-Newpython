import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.brokers.dhan.http_client import dhan_http_client
from app.brokers.models import BrokerAccount
from app.brokers.service import connect_broker, get_active_broker_for_user
from app.core.exceptions import ValidationError, BrokerError

logger = logging.getLogger(__name__)

class DhanAuthService:
    """Service handling all Dhan HQ authentication flows (TOTP, Token Renewal, Consent, Direct Connect)."""

    @staticmethod
    async def generate_token_totp(db: AsyncSession, user_id: int, client_id: str, pin: str, totp: str) -> BrokerAccount:
        """Generates access token using Client ID, PIN, and TOTP via POST /app/generateAccessToken."""
        payload = {
            "dhanClientId": client_id,
            "pin": pin,
            "totp": totp
        }
        res_data = await dhan_http_client._request(
            method="POST",
            path="/app/generateAccessToken",
            payload=payload,
            is_auth_api=True
        )

        access_token = res_data.get("accessToken") or res_data.get("access_token")
        if not access_token:
            raise ValidationError("Dhan HQ failed to return valid accessToken in TOTP generation")

        now_utc = datetime.now(timezone.utc)
        expiry = now_utc + timedelta(days=30)

        credentials = {
            "clientId": client_id,
            "accessToken": access_token,
            "expiryTime": expiry.isoformat()
        }

        account = await connect_broker(db, user_id, "DHAN", credentials)
        return account

    @staticmethod
    async def renew_token(db: AsyncSession, user_id: int) -> BrokerAccount:
        """Renews existing active Dhan access token via GET /v2/RenewToken."""
        account = await get_active_broker_for_user(db, user_id)
        creds = account.credentials
        
        res_data = await dhan_http_client._request(
            method="GET",
            path="/v2/RenewToken",
            credentials=creds
        )

        new_token = res_data.get("accessToken") or res_data.get("access_token")
        if new_token:
            creds["accessToken"] = new_token
            now_utc = datetime.now(timezone.utc)
            expiry = now_utc + timedelta(days=30)
            creds["expiryTime"] = expiry.isoformat()
            account.set_credentials(creds)
            account.expiry_time = expiry
            db.add(account)
            await db.flush()

        return account

    @staticmethod
    async def set_static_ip(db: AsyncSession, user_id: int, primary_ip: str, secondary_ip: Optional[str] = None) -> BrokerAccount:
        """Configures static IP routing for Dhan HQ account."""
        account = await get_active_broker_for_user(db, user_id)
        creds = account.credentials
        
        payload = {
            "dhanClientId": account.account_client_id,
            "ip": primary_ip,
            "secondaryIp": secondary_ip
        }
        
        try:
            await dhan_http_client._request(
                method="POST",
                path="/v2/ip/setIP",
                credentials=creds,
                payload=payload
            )
        except Exception as e:
            logger.warning("Failed to register IP with Dhan HQ server: %s", str(e))

        account.primary_ip = primary_ip
        account.secondary_ip = secondary_ip
        db.add(account)
        await db.flush()
        return account


dhan_auth_service = DhanAuthService()

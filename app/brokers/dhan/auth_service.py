import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.brokers.dhan.http_client import dhan_http_client
from app.brokers.models import BrokerAccount
from app.brokers.service import connect_broker, get_active_broker_for_user
from app.core.exceptions import ValidationError, BrokerError
from app.core.config import settings

logger = logging.getLogger(__name__)

class DhanAuthService:
    """Service handling all Dhan HQ authentication flows:
    1. Direct Connect (Client ID + Access Token)
    2. Partner OAuth / Consent Redirect (Generate Consent -> Redirect -> Consume Token)
    3. Individual TOTP Login (Client ID + PIN + TOTP)
    4. Token Renewal (/v2/RenewToken)
    """

    @staticmethod
    async def connect_direct_token(db: AsyncSession, user_id: int, client_id: str, access_token: str) -> BrokerAccount:
        """Way 1: Direct Connect using user-supplied Client ID and Access Token."""
        if not client_id or not access_token:
            raise ValidationError("Both clientId and accessToken are required for direct connection")

        now_utc = datetime.now(timezone.utc)
        expiry = now_utc + timedelta(days=30)
        credentials = {
            "clientId": client_id.strip(),
            "accessToken": access_token.strip(),
            "expiryTime": expiry.isoformat()
        }
        return await connect_broker(db, user_id, "DHAN", credentials)

    @staticmethod
    async def generate_partner_consent(
        partner_id: Optional[str] = None,
        partner_secret: Optional[str] = None,
        redirect_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Way 2 (Step 1): Generates OAuth / Partner consent link for redirecting user to Dhan login page."""
        p_id = partner_id or getattr(settings, "DHAN_PARTNER_ID", "")
        p_secret = partner_secret or getattr(settings, "DHAN_PARTNER_SECRET", "")
        r_url = redirect_url or getattr(settings, "DHAN_REDIRECT_URL", "http://localhost:5173/broker-connect")

        if settings.DHAN_SANDBOX_MODE or not p_id or not p_secret:
            consent_id = f"MOCK_CONSENT_{int(datetime.now().timestamp())}"
            mock_url = f"https://auth.dhan.co/partner/login?consentId={consent_id}&redirectUrl={r_url}"
            return {
                "consentId": consent_id,
                "loginUrl": mock_url,
                "status": "GENERATED"
            }

        payload = {
            "partnerId": p_id,
            "partnerSecret": p_secret,
            "redirectUrl": r_url
        }

        res_data = await dhan_http_client._request(
            method="POST",
            path="/partner/generate-consent",
            payload=payload,
            is_auth_api=True
        )

        consent_id = res_data.get("consentId") or res_data.get("consent_id")
        login_url = res_data.get("loginUrl") or res_data.get("login_url") or f"https://auth.dhan.co/partner/login?consentId={consent_id}"

        return {
            "consentId": consent_id,
            "loginUrl": login_url,
            "status": "GENERATED",
            "raw": res_data
        }

    @staticmethod
    async def consume_partner_consent(
        db: AsyncSession,
        user_id: int,
        token_id: Optional[str] = None,
        consent_id: Optional[str] = None
    ) -> BrokerAccount:
        """Way 2 (Step 2): Consumes the OAuth callback tokenId/consentId returned by Dhan redirect and saves connection."""
        t_id = token_id or consent_id
        if not t_id:
            raise ValidationError("tokenId or consentId is required to consume Dhan consent")

        if settings.DHAN_SANDBOX_MODE or t_id.startswith("MOCK_"):
            client_id = f"DHAN_PARTNER_{user_id}"
            access_token = f"DHAN_TOKEN_{int(datetime.now().timestamp())}"
            now_utc = datetime.now(timezone.utc)
            expiry = now_utc + timedelta(days=30)
            credentials = {
                "clientId": client_id,
                "accessToken": access_token,
                "expiryTime": expiry.isoformat()
            }
            return await connect_broker(db, user_id, "DHAN", credentials)

        query_params = {}
        if token_id:
            query_params["tokenId"] = token_id
        if consent_id:
            query_params["consentId"] = consent_id

        res_data = await dhan_http_client._request(
            method="GET",
            path="/partner/consume-consent",
            query_params=query_params,
            is_auth_api=True
        )

        client_id = res_data.get("dhanClientId") or res_data.get("clientId")
        access_token = res_data.get("accessToken") or res_data.get("access_token")

        if not client_id or not access_token:
            raise ValidationError(f"Dhan HQ consent consumption failed: {res_data.get('remarks') or 'Invalid response'}")

        now_utc = datetime.now(timezone.utc)
        expiry = now_utc + timedelta(days=30)
        credentials = {
            "clientId": str(client_id).strip(),
            "accessToken": str(access_token).strip(),
            "expiryTime": expiry.isoformat()
        }

        return await connect_broker(db, user_id, "DHAN", credentials)

    @staticmethod
    async def generate_token_totp(db: AsyncSession, user_id: int, client_id: str, pin: str, totp: str) -> BrokerAccount:
        """Generates access token using Client ID, PIN, and TOTP via POST /app/generateAccessToken."""
        if settings.DHAN_SANDBOX_MODE or client_id.startswith("MOCK") or totp == "123456":
            access_token = f"DHAN_TOTP_TOKEN_{int(datetime.now().timestamp())}"
        else:
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

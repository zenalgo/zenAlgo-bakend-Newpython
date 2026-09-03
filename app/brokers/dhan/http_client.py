import httpx
import asyncio
import logging
from typing import Dict, Any, Optional
from app.core.config import settings
from app.core.redis import redis_manager
from app.brokers.dhan.exceptions import DhanAPIError, DhanAuthenticationError, DhanTimeoutException

logger = logging.getLogger(__name__)

class DhanHttpClient:
    """Async HTTP client for interacting with Dhan HQ Open API v2.
    Uses httpx.AsyncClient with connection pooling, Redis Token Bucket rate limiting, and error parsing.
    """
    def __init__(
        self,
        base_url: Optional[str] = None,
        auth_base_url: Optional[str] = None,
        timeout: float = 10.0,
        max_connections: int = 100,
        max_keepalive: int = 20
    ):
        self.base_url = (base_url or getattr(settings, "DHAN_API_BASE_URL", "https://api.dhan.co/v2")).rstrip("/")
        self.auth_base_url = (auth_base_url or getattr(settings, "DHAN_AUTH_BASE_URL", "https://auth.dhan.co")).rstrip("/")
        self.timeout = timeout
        
        limits = httpx.Limits(max_connections=max_connections, max_keepalive_connections=max_keepalive)
        self.client = httpx.AsyncClient(limits=limits, timeout=self.timeout)
        self._local_semaphore = asyncio.Semaphore(25)

    async def _request(
        self,
        method: str,
        path: str,
        credentials: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        query_params: Optional[Dict[str, Any]] = None,
        is_auth_api: bool = False
    ) -> Any:
        """Executes an async HTTP request to Dhan HQ with rate limits and error handling."""
        async with self._local_semaphore:
            # Enforce Redis Token Bucket rate limit
            rate_key = f"rate_limit:dhan:{'auth' if is_auth_api else 'api'}"
            allowed = await redis_manager.acquire_token_bucket(rate_key, rate=10, capacity=10)
            if not allowed:
                await asyncio.sleep(0.1)

            base_target = self.auth_base_url if is_auth_api else self.base_url
            clean_path = path
            if base_target.endswith("/v2") and clean_path.startswith("/v2"):
                clean_path = clean_path[3:]
            if not clean_path.startswith("/"):
                clean_path = "/" + clean_path
            url = f"{base_target}{clean_path}"

            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json"
            }

            if credentials:
                access_token = credentials.get("accessToken") or credentials.get("access_token")
                client_id = credentials.get("clientId") or credentials.get("client_id") or credentials.get("dhanClientId")

                if access_token:
                    headers["access-token"] = str(access_token).strip()
                if client_id:
                    headers["client-id"] = str(client_id).strip()
                    headers["dhanClientId"] = str(client_id).strip()

            logger.info("Executing Dhan HTTP %s request to %s", method.upper(), path)

            try:
                response = await self.client.request(
                    method=method.upper(),
                    url=url,
                    headers=headers,
                    json=payload,
                    params=query_params
                )
            except httpx.TimeoutException as ex:
                logger.error("Dhan HTTP timeout [%s %s]: %s", method, url, str(ex))
                raise DhanTimeoutException(f"Request to Dhan timed out: {str(ex)}")
            except httpx.RequestError as ex:
                logger.error("Dhan HTTP network failure [%s %s]: %s", method, url, str(ex))
                raise DhanAPIError(f"Network failure connecting to Dhan: {str(ex)}", code="DHAN_NETWORK_ERROR")

            try:
                data = response.json()
            except Exception:
                data = {"raw_text": response.text}

            if response.status_code in (401, 403):
                logger.warning("Dhan authentication failed [%s %s]: %s", response.status_code, url, data)
                raise DhanAuthenticationError(
                    message=f"Dhan session invalid or expired: {data.get('remarks') or data.get('message') or response.text}"
                )

            if response.is_error:
                error_msg = data.get("remarks") or data.get("message") or data.get("error") or response.text
                error_code = data.get("errorCode") or data.get("code") or "DHAN_REJECTED"
                logger.error("Dhan API HTTP %s Error [%s]: %s", response.status_code, error_code, error_msg)
                raise DhanAPIError(
                    message=f"Dhan API returned error: {error_msg}",
                    code=error_code,
                    status_code=response.status_code,
                    raw_response=data
                )

            return data

    async def close(self):
        """Closes the underlying httpx client."""
        await self.client.aclose()


dhan_http_client = DhanHttpClient()

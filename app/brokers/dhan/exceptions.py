from app.core.exceptions import BrokerError, AuthenticationError

class DhanAPIError(BrokerError):
    """Base exception for Dhan API errors."""
    def __init__(self, message: str, code: str = "DHAN_ERROR", status_code: int = 400, raw_response: dict = None):
        super().__init__(message, code=code, status_code=status_code)
        self.raw_response = raw_response or {}

class DhanAuthenticationError(AuthenticationError):
    """Exception raised when Dhan authentication/access token fails or expires."""
    def __init__(self, message: str = "Dhan access token is invalid or expired", code: str = "DHAN_AUTH_EXPIRED"):
        super().__init__(message, code=code)

class DhanTimeoutException(BrokerError):
    """Exception raised when a request to Dhan HQ times out."""
    def __init__(self, message: str = "Dhan API request timed out", code: str = "DHAN_TIMEOUT"):
        super().__init__(message, code=code, status_code=504)

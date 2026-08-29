import uuid
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from typing import Optional, Any

class ZenAlgoException(Exception):
    """Base exception for ZenAlgo platform."""
    def __init__(self, message: str, code: str = "INTERNAL_SERVER_ERROR", status_code: int = 500, data: Optional[Any] = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.data = data

class AuthenticationError(ZenAlgoException):
    def __init__(self, message: str = "Invalid credentials", code: str = "UNAUTHENTICATED", data: Optional[Any] = None):
        super().__init__(message, code, 401, data)

class AuthorizationError(ZenAlgoException):
    def __init__(self, message: str = "Access denied", code: str = "FORBIDDEN", data: Optional[Any] = None):
        super().__init__(message, code, 403, data)

class ResourceNotFoundError(ZenAlgoException):
    def __init__(self, message: str = "Resource not found", code: str = "NOT_FOUND", data: Optional[Any] = None):
        super().__init__(message, code, 404, data)

class ConflictError(ZenAlgoException):
    def __init__(self, message: str = "Resource conflict", code: str = "CONFLICT", data: Optional[Any] = None):
        super().__init__(message, code, 409, data)

class ValidationError(ZenAlgoException):
    def __init__(self, message: str = "Validation failed", code: str = "BAD_REQUEST", data: Optional[Any] = None):
        super().__init__(message, code, 400, data)

class SubscriptionError(ZenAlgoException):
    def __init__(self, message: str, code: str = "SUBSCRIPTION_ERROR", status_code: int = 400, data: Optional[Any] = None):
        super().__init__(message, code, status_code, data)

class BrokerError(ZenAlgoException):
    def __init__(self, message: str, code: str = "BROKER_ERROR", status_code: int = 400, data: Optional[Any] = None):
        super().__init__(message, code, status_code, data)

class StrategyExecutionError(ZenAlgoException):
    def __init__(self, message: str, code: str = "EXECUTION_ERROR", status_code: int = 400, data: Optional[Any] = None):
        super().__init__(message, code, status_code, data)

class DuplicateRequestException(ZenAlgoException):
    def __init__(self, message: str = "Duplicate request", code: str = "DUPLICATE_REQUEST", data: Optional[Any] = None):
        super().__init__(message, code, 409, data)

def setup_exception_handlers(app):
    @app.exception_handler(ZenAlgoException)
    async def zenalgo_exception_handler(request: Request, exc: ZenAlgoException):
        from fastapi.encoders import jsonable_encoder
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "code": exc.code,
                "message": exc.message,
                "data": jsonable_encoder(exc.data) if exc.data is not None else None,
                "requestId": request_id
            }
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        errors = []
        for error in exc.errors():
            loc = ".".join(str(x) for x in error.get("loc", []))
            errors.append({
                "field": loc,
                "message": error.get("msg", "Validation error")
            })
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "code": "BAD_REQUEST",
                "message": "Validation failed",
                "data": errors,
                "requestId": request_id
            }
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        code = "HTTP_ERROR"
        if exc.status_code == 404:
            code = "NOT_FOUND"
        elif exc.status_code == 401:
            code = "UNAUTHENTICATED"
        elif exc.status_code == 403:
            code = "FORBIDDEN"
        elif exc.status_code == 400:
            code = "BAD_REQUEST"
            
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "code": code,
                "message": exc.detail,
                "data": None,
                "requestId": request_id
            }
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        # Print for local debugging
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred. Please contact support.",
                "data": None,
                "requestId": request_id
            }
        )

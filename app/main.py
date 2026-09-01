import uuid
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.exceptions import setup_exception_handlers

# Pre-import all SQLAlchemy models to register them on Base metadata registry
import app.users.models
import app.execution.models
import app.strategies.models
import app.wallets.models
import app.subscriptions.models

# Import routers
from app.auth.router import router as auth_router
from app.users.router import router as users_router
from app.wallets.router import router as wallets_router
from app.subscriptions.router import trader_router, admin_router as sub_admin_router
from app.strategies.router import router as strategies_router, rules_router, strategy_api_router
from app.brokers.router import router as brokers_router

app = FastAPI(
    title="ZenAlgo Platform Backend",
    description="High-performance algorithmic copy-trading backend migrated to FastAPI",
    version="1.0.0"
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware to append a unique request ID to each incoming request context
@app.middleware("http")
async def add_request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    return response

# Register customized validation and domain exception handlers
setup_exception_handlers(app)

# Register routers
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(wallets_router)
app.include_router(trader_router)
app.include_router(sub_admin_router)
app.include_router(strategies_router)
app.include_router(rules_router)
app.include_router(strategy_api_router)
app.include_router(brokers_router)

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "service": "zenalgo-backend"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.APP_PORT, reload=True)

import uuid
from fastapi import FastAPI, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.exceptions import setup_exception_handlers

# Pre-import all SQLAlchemy models to register them on Base metadata registry
import app.users.models
import app.execution.models
import app.strategies.models
import app.wallets.models
import app.subscriptions.models
import app.instruments.models

# Import routers
from app.auth.router import router as auth_router
from app.users.router import router as users_router
from app.wallets.router import router as wallets_router
from app.subscriptions.router import trader_router, admin_router as sub_admin_router
from app.strategies.router import router as strategies_router, rules_router, strategy_api_router
from app.brokers.router import router as brokers_router
from app.execution.router import router as execution_router, trader_exec_router
from app.partners.router import router as partners_router
from app.instruments.router import router as instruments_router
from app.instruments.service import seed_instruments_if_empty
from app.admin.connected_users_router import router as admin_broker_users_router
from app.admin.reports_router import router as admin_reports_router
from app.calculation_engine.router import router as calc_engine_router

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

from app.brokers.bootstrap import bootstrap_broker_adapters

# Bootstrap broker adapter registrations into registry
bootstrap_broker_adapters()

# Register customized validation and domain exception handlers
setup_exception_handlers(app)


import asyncio
from app.core.redis import redis_manager
from app.execution.reconciliation import order_reconciliation_worker
from app.brokers.websocket import router as ws_router

@app.on_event("startup")
async def on_startup():
    await redis_manager.init_redis()
    asyncio.create_task(order_reconciliation_worker.start())
    try:
        from app.core.database import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            await seed_instruments_if_empty(session)
    except Exception as e:
        print(f"Instrument seeder notice: {e}")

@app.on_event("shutdown")
async def on_shutdown():
    order_reconciliation_worker.stop()
    await redis_manager.close()

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
app.include_router(execution_router)
app.include_router(trader_exec_router)
app.include_router(partners_router, prefix="/api/v1")
app.include_router(instruments_router, prefix="/api/v1")
app.include_router(ws_router)
app.include_router(calc_engine_router, prefix="/api/v1")
app.include_router(admin_broker_users_router)
app.include_router(admin_reports_router)

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "service": "zenalgo-backend"}

@app.websocket("/ws/calc-engine")
async def ws_calc_engine_root(websocket: WebSocket):
    from app.calculation_engine.registry import CalcEngineWSManager
    await CalcEngineWSManager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except Exception:
        CalcEngineWSManager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.APP_PORT, reload=True)

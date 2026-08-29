from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from typing import List

from app.core.database import get_db
from app.core.schemas import ApiResponse
from app.core.dependencies import require_permission
from app.wallets.schemas import WalletDto, WalletTransactionDto, CreditDebitRequest
from app.wallets import service

router = APIRouter(prefix="/api/v1/wallets", tags=["Wallet System"])

@router.get("/me", response_model=ApiResponse[WalletDto])
async def get_my_wallet(
    request: Request,
    current_user = Depends(require_permission("ACCOUNT_READ")),
    db: AsyncSession = Depends(get_db)
):
    wallet = await service.get_wallet_by_user_id(db, current_user.id)
    wallet_dto = WalletDto.model_validate(wallet)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Wallet retrieved successfully",
        data=wallet_dto,
        requestId=request_id
    )

@router.get("/me/transactions", response_model=ApiResponse[List[WalletTransactionDto]])
async def get_my_transactions(
    request: Request,
    current_user = Depends(require_permission("WALLET_READ")),
    db: AsyncSession = Depends(get_db)
):
    transactions = await service.get_transaction_history(db, current_user.id)
    tx_dtos = [WalletTransactionDto.model_validate(tx) for tx in transactions]
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Transaction history retrieved successfully",
        data=tx_dtos,
        requestId=request_id
    )

@router.post("/me/deposit", response_model=ApiResponse[WalletTransactionDto])
async def deposit(
    request: Request,
    body: CreditDebitRequest,
    current_user = Depends(require_permission("WALLET_WRITE")),
    db: AsyncSession = Depends(get_db)
):
    tx = await service.credit(
        db,
        user_id=current_user.id,
        amount=body.amount,
        tx_type="DEPOSIT",
        description=body.description or "Wallet Deposit",
        reference_type=body.referenceType,
        reference_id=body.referenceId,
        idempotency_key=body.idempotencyKey
    )
    tx_dto = WalletTransactionDto.model_validate(tx)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Wallet credited successfully",
        data=tx_dto,
        requestId=request_id
    )

@router.post("/me/withdraw", response_model=ApiResponse[WalletTransactionDto])
async def withdraw(
    request: Request,
    body: CreditDebitRequest,
    current_user = Depends(require_permission("WALLET_WRITE")),
    db: AsyncSession = Depends(get_db)
):
    tx = await service.debit(
        db,
        user_id=current_user.id,
        amount=body.amount,
        tx_type="WITHDRAWAL",
        description=body.description or "Wallet Withdrawal",
        reference_type=body.referenceType,
        reference_id=body.referenceId,
        idempotency_key=body.idempotencyKey
    )
    tx_dto = WalletTransactionDto.model_validate(tx)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Wallet debited successfully",
        data=tx_dto,
        requestId=request_id
    )

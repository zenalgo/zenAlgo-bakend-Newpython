from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

from app.wallets.models import Wallet, WalletTransaction
from app.core.exceptions import ResourceNotFoundError, ValidationError

async def create_wallet(db: AsyncSession, user) -> Wallet:
    """Initializes a new wallet for a user with 0.00 balance."""
    wallet = Wallet(
        user_id=user.id,
        balance=Decimal("0.00"),
        currency="INR",
        version=0
    )
    db.add(wallet)
    await db.flush()
    return wallet

async def get_wallet_by_user_id(db: AsyncSession, user_id: int) -> Wallet:
    """Finds a wallet by user ID."""
    stmt = select(Wallet).where(Wallet.user_id == user_id)
    res = await db.execute(stmt)
    wallet = res.scalar_one_or_none()
    if not wallet:
        raise ResourceNotFoundError("Wallet not found for this user")
    return wallet

async def get_transaction_history(db: AsyncSession, user_id: int) -> List[WalletTransaction]:
    """Retrieves all transaction logs for a user."""
    wallet = await get_wallet_by_user_id(db, user_id)
    stmt = select(WalletTransaction).where(WalletTransaction.wallet_id == wallet.id).order_by(WalletTransaction.created_at.desc())
    res = await db.execute(stmt)
    return list(res.scalars().all())

async def credit(
    db: AsyncSession,
    user_id: int,
    amount: Decimal,
    tx_type: str,
    description: str,
    reference_type: str = None,
    reference_id: str = None,
    idempotency_key: str = None
) -> WalletTransaction:
    """Credits a user's wallet safely, locking the row and verifying idempotency."""
    if amount <= 0:
        raise ValidationError("Amount must be greater than zero")

    # Idempotency safety check
    if idempotency_key:
        stmt = select(WalletTransaction).where(WalletTransaction.idempotency_key == idempotency_key)
        res = await db.execute(stmt)
        existing_tx = res.scalar_one_or_none()
        if existing_tx:
            # Return existing transaction instead of processing again
            return existing_tx

    # Lock wallet row
    stmt = select(Wallet).where(Wallet.user_id == user_id).with_for_update()
    res = await db.execute(stmt)
    wallet = res.scalar_one_or_none()
    if not wallet:
        raise ResourceNotFoundError("Wallet not found for this user")

    balance_before = wallet.balance
    balance_after = balance_before + amount

    # Update balance
    wallet.balance = balance_after
    wallet.version += 1
    db.add(wallet)

    # Log transaction
    tx = WalletTransaction(
        wallet_id=wallet.id,
        amount=amount,
        balance_before=balance_before,
        balance_after=balance_after,
        transaction_type=tx_type,
        description=description,
        reference_type=reference_type,
        reference_id=reference_id,
        idempotency_key=idempotency_key,
        status="COMPLETED"
    )
    db.add(tx)
    await db.flush()
    return tx

async def debit(
    db: AsyncSession,
    user_id: int,
    amount: Decimal,
    tx_type: str,
    description: str,
    reference_type: str = None,
    reference_id: str = None,
    idempotency_key: str = None
) -> WalletTransaction:
    """Debits a user's wallet safely, ensuring sufficient balance under locks."""
    if amount <= 0:
        raise ValidationError("Amount must be greater than zero")

    # Idempotency check
    if idempotency_key:
        stmt = select(WalletTransaction).where(WalletTransaction.idempotency_key == idempotency_key)
        res = await db.execute(stmt)
        existing_tx = res.scalar_one_or_none()
        if existing_tx:
            return existing_tx

    # Lock wallet row
    stmt = select(Wallet).where(Wallet.user_id == user_id).with_for_update()
    res = await db.execute(stmt)
    wallet = res.scalar_one_or_none()
    if not wallet:
        raise ResourceNotFoundError("Wallet not found for this user")

    if wallet.balance < amount:
        raise ValidationError("Insufficient wallet balance")

    balance_before = wallet.balance
    balance_after = balance_before - amount

    # Update balance
    wallet.balance = balance_after
    wallet.version += 1
    db.add(wallet)

    # Log transaction
    tx = WalletTransaction(
        wallet_id=wallet.id,
        amount=amount,
        balance_before=balance_before,
        balance_after=balance_after,
        transaction_type=tx_type,
        description=description,
        reference_type=reference_type,
        reference_id=reference_id,
        idempotency_key=idempotency_key,
        status="COMPLETED"
    )
    db.add(tx)
    await db.flush()
    return tx

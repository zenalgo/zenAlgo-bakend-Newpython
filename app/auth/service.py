import random
import string
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

from app.users.models import User, UserRole
from app.auth.schemas import RegisterRequest, LoginRequest, TokenRefreshRequest, AuthResponse
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from app.core.exceptions import ValidationError, AuthenticationError, ResourceNotFoundError, DuplicateRequestException
from app.wallets.service import create_wallet

def get_role_permissions(role: str) -> List[str]:
    """Maps UserRole enum to permission strings."""
    if role in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
        return [
            "USER_READ", "USER_WRITE", "ACCOUNT_READ", "ACCOUNT_WRITE",
            "TRADE_READ", "TRADE_EXECUTE", "WALLET_READ", "WALLET_WRITE",
            "PORTFOLIO_READ"
        ]
    elif role == UserRole.TRADER:
        return ["ACCOUNT_READ", "TRADE_READ", "TRADE_EXECUTE"]
    elif role in [UserRole.USER, UserRole.PARTNER]:
        return ["ACCOUNT_READ", "PORTFOLIO_READ", "TRADE_READ"]
    return []

async def generate_unique_referral_code(db: AsyncSession) -> str:
    """Generates a random UNIQUE referral code matching: REF-[A-Z0-9]{6}."""
    chars = string.ascii_uppercase + string.digits
    while True:
        code = "REF-" + "".join(random.choices(chars, k=6))
        # Check uniqueness
        stmt = select(User).where(User.referral_code == code)
        result = await db.execute(stmt)
        if not result.scalar_one_or_none():
            return code

async def register_user(db: AsyncSession, request: RegisterRequest) -> User:
    """Registers a new User, inactive by default, and provisions a wallet."""
    # Uniqueness check
    stmt = select(User).where(User.email == request.email)
    res = await db.execute(stmt)
    if res.scalar_one_or_none():
        raise DuplicateRequestException("Email address already registered")

    referrer = None
    if request.referredByCode:
        stmt = select(User).where(User.referral_code == request.referredByCode)
        res = await db.execute(stmt)
        referrer = res.scalar_one_or_none()
        if not referrer:
            raise ResourceNotFoundError("Referral code not found")

    referral_code = await generate_unique_referral_code(db)
    
    user = User(
        email=request.email,
        password_hash=hash_password(request.password),
        role=UserRole.USER,
        is_active=False, # Self-registered are inactive by default
        referral_code=referral_code,
        referred_by_id=referrer.id if referrer else None,
        first_name=request.firstName,
        last_name=request.lastName
    )
    db.add(user)
    await db.flush() # Flush to get user.id for wallet foreign key
    
    # Initialize wallet
    await create_wallet(db, user)
    return user

async def login_user(db: AsyncSession, request: LoginRequest) -> AuthResponse:
    """Handles standard trader/user login, rejecting administrative roles."""
    stmt = select(User).where(User.email == request.email)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    
    if not user:
        raise ResourceNotFoundError("User not found")
        
    if not user.is_active:
        raise AuthenticationError("User is deactivated", code="DEACTIVATED")

    if not verify_password(user.password_hash, request.password):
        raise AuthenticationError("Invalid password", code="BAD_CREDENTIALS")

    # Reject administrative logins from standard portal
    if user.role in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise AuthenticationError("Use the Admin Portal to log in", code="BAD_CREDENTIALS")

    permissions = get_role_permissions(user.role.value)
    access_token = create_access_token(user.email, user.role.value, permissions)
    refresh_token = create_refresh_token(user.email)
    
    return AuthResponse(
        email=user.email,
        role=user.role.value,
        accessToken=access_token,
        refreshToken=refresh_token
    )

async def login_admin(db: AsyncSession, request: LoginRequest) -> AuthResponse:
    """Handles administrative login, strictly requiring ADMIN/SUPER_ADMIN roles."""
    stmt = select(User).where(User.email == request.email)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    
    if not user:
        raise ResourceNotFoundError("User not found")
        
    if not user.is_active:
        raise AuthenticationError("User is deactivated", code="DEACTIVATED")

    if not verify_password(user.password_hash, request.password):
        raise AuthenticationError("Invalid password", code="BAD_CREDENTIALS")

    # Enforce administrative privileges
    if user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise AuthenticationError("Access denied: Not an administrator account", code="BAD_CREDENTIALS")

    permissions = get_role_permissions(user.role.value)
    access_token = create_access_token(user.email, user.role.value, permissions)
    refresh_token = create_refresh_token(user.email)
    
    return AuthResponse(
        email=user.email,
        role=user.role.value,
        accessToken=access_token,
        refreshToken=refresh_token
    )

async def refresh_session_token(db: AsyncSession, request: TokenRefreshRequest) -> AuthResponse:
    """Refreshes access and refresh tokens using a valid refresh token."""
    payload = decode_token(request.refreshToken)
    if not payload or "sub" not in payload:
        raise AuthenticationError("Invalid or expired refresh token", code="BAD_CREDENTIALS")
        
    email = payload["sub"]
    stmt = select(User).where(User.email == email)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    
    if not user:
        raise ResourceNotFoundError("User not found")
        
    if not user.is_active:
        raise AuthenticationError("User is deactivated", code="USER_INACTIVE")

    permissions = get_role_permissions(user.role.value)
    access_token = create_access_token(user.email, user.role.value, permissions)
    refresh_token = create_refresh_token(user.email)
    
    return AuthResponse(
        email=user.email,
        role=user.role.value,
        accessToken=access_token,
        refreshToken=refresh_token
    )

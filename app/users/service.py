from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional

from app.users.models import User, UserRole
from app.users.schemas import ProvisionUserRequest, UserStatusUpdateRequest, UserDto
from app.core.security import hash_password
from app.core.exceptions import ResourceNotFoundError, AuthorizationError, DuplicateRequestException
from app.auth.service import generate_unique_referral_code
from app.wallets.service import create_wallet

async def provision_user(db: AsyncSession, request: ProvisionUserRequest, executor_email: str) -> User:
    """Provisions a new active user, validating executor hierarchical permissions."""
    stmt = select(User).where(User.email == executor_email)
    res = await db.execute(stmt)
    executor = res.scalar_one_or_none()
    if not executor:
        raise ResourceNotFoundError("Executor Not Found")

    executor_role = executor.role
    target_role = request.role

    # Privilege checking
    if executor_role == UserRole.ADMIN:
        if target_role in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
            raise AuthorizationError("Administrators can only provision TRADER or USER credentials")
    elif executor_role != UserRole.SUPER_ADMIN:
        raise AuthorizationError("You do not have permissions to provision user accounts.")

    # Unique email check
    stmt = select(User).where(User.email == request.email)
    res = await db.execute(stmt)
    if res.scalar_one_or_none():
        raise DuplicateRequestException("Email address already Registered")

    referrer = None
    if request.referredByCode:
        stmt = select(User).where(User.referral_code == request.referredByCode)
        res = await db.execute(stmt)
        referrer = res.scalar_one_or_none()
        if not referrer:
            raise ResourceNotFoundError(f"Referral code not found: {request.referredByCode}")

    referral_code = await generate_unique_referral_code(db)
    
    newUser = User(
        email=request.email,
        password_hash=hash_password(request.password),
        role=target_role,
        is_active=False, # Provisioned users are inactive by default until activated
        referral_code=referral_code,
        referred_by_id=executor.id, # The executor becomes the referrer
        first_name=request.firstName,
        last_name=request.lastName
    )
    db.add(newUser)
    await db.commit()
    await db.refresh(newUser)
    
    # Initialize wallet
    await create_wallet(db, newUser)
    return newUser

async def get_all_users(
    db: AsyncSession,
    page: int = 0,
    size: int = 50,
    search: Optional[str] = None,
    role: Optional[str] = None,
    is_active: Optional[bool] = None
) -> List[UserDto]:
    """Retrieves all registered users mapped to UserDto with pagination and filtering."""
    stmt = select(User)
    
    if search:
        term = f"%{search.strip()}%"
        stmt = stmt.where(User.email.ilike(term) | User.first_name.ilike(term) | User.last_name.ilike(term))
    if role:
        stmt = stmt.where(User.role == role)
    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)

    stmt = stmt.order_by(User.id.desc()).offset(page * size).limit(size)
    result = await db.execute(stmt)
    users = result.scalars().all()
    return [UserDto.model_validate(user) for user in users]

async def update_user_status(db: AsyncSession, target_user_id: int, request: UserStatusUpdateRequest, executor_email: str) -> User:
    """Updates activation status, preventing self-lockout and enforcing hierarchy rules."""
    stmt = select(User).where(User.email == executor_email)
    res = await db.execute(stmt)
    executor = res.scalar_one_or_none()
    if not executor:
        raise ResourceNotFoundError("Executor not found")

    stmt = select(User).where(User.id == target_user_id)
    res = await db.execute(stmt)
    target = res.scalar_one_or_none()
    if not target:
        raise ResourceNotFoundError("User to update not found")

    # Lockout Prevention
    if executor.id == target.id:
        raise AuthorizationError("You cannot activate or deactivate your own account.")

    executor_role = executor.role
    target_role = target.role

    # Hierarchy verification
    if executor_role == UserRole.ADMIN:
        if target_role in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
            raise AuthorizationError("Administrators can only update active status of TRADER or USER accounts.")
    elif executor_role != UserRole.SUPER_ADMIN:
        raise AuthorizationError("You do not have permissions to modify user active states.")

    target.is_active = request.is_active_val
    db.add(target)
    await db.commit()
    await db.refresh(target)
    return target

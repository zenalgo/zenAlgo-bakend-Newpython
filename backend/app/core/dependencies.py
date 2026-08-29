from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

from app.core.database import get_db
from app.core.security import decode_token
from app.core.exceptions import AuthenticationError, AuthorizationError

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
):
    """Resolves JWT token, verifies validity and loads user context."""
    token = credentials.credentials
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        raise AuthenticationError("Invalid or expired session token", code="UNAUTHENTICATED")
        
    email = payload["sub"]
    
    # Lazy import to prevent circular dependencies
    from app.users.models import User
    
    stmt = select(User).where(User.email == email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        raise AuthenticationError("User account not found", code="USER_NOT_FOUND")
        
    if not user.is_active:
        raise AuthenticationError("User account is deactivated", code="USER_INACTIVE")
        
    return user

def require_role(roles: List[str]):
    """Requires user to match one of the specified roles."""
    async def dependency(current_user = Depends(get_current_user)):
        if current_user.role not in roles:
            raise AuthorizationError("Access denied: Insufficient privileges", code="FORBIDDEN")
        return current_user
    return dependency

def require_permission(permission: str):
    """Requires the user context to have the specified permission."""
    async def dependency(current_user = Depends(get_current_user), credentials: HTTPAuthorizationCredentials = Depends(security)):
        token = credentials.credentials
        payload = decode_token(token)
        if not payload or "permissions" not in payload or permission not in payload["permissions"]:
            raise AuthorizationError("Access denied: Insufficient privileges", code="FORBIDDEN")
        return current_user
    return dependency

# Common guards
require_admin = require_role(["ADMIN", "SUPER_ADMIN"])
require_trader = require_role(["TRADER", "USER", "PARTNER", "ADMIN", "SUPER_ADMIN"])

from datetime import datetime, timedelta, timezone
from typing import Optional, List
import jwt
import base64
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import settings

# Argon2id configuration matching Spring Security's defaults
ph = PasswordHasher(
    time_cost=2,
    memory_cost=16384,
    parallelism=1,
    hash_len=32,
    salt_len=16
)

# Decode key if Base64, otherwise fallback to utf-8 bytes
try:
    JWT_SECRET_KEY = base64.b64decode(settings.JWT_SECRET)
except Exception:
    JWT_SECRET_KEY = settings.JWT_SECRET.encode()

def hash_password(password: str) -> str:
    """Argon2id hash generation."""
    return ph.hash(password)

def verify_password(hashed_password: str, password: str) -> bool:
    """Verifies Argon2id hash."""
    try:
        return ph.verify(hashed_password, password)
    except VerifyMismatchError:
        return False

def create_access_token(email: str, role: str, permissions: List[str]) -> str:
    """Generates JWT Access Token with role and permissions claims."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {
        "sub": email,
        "role": role,
        "permissions": permissions,
        "iat": datetime.now(timezone.utc),
        "exp": expire
    }
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm="HS256")
    return encoded_jwt

def create_refresh_token(email: str) -> str:
    """Generates JWT Refresh Token."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_REFRESH_TOKEN_EXPIRE_MINUTES)
    to_encode = {
        "sub": email,
        "iat": datetime.now(timezone.utc),
        "exp": expire
    }
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm="HS256")
    return encoded_jwt

def decode_token(token: str) -> Optional[dict]:
    """Decodes and validates a JWT token."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.PyJWTError:
        return None

import json
import hashlib
from cryptography.fernet import Fernet

def _get_fernet_key() -> bytes:
    key_hash = hashlib.sha256(settings.JWT_SECRET.encode()).digest()
    return base64.urlsafe_b64encode(key_hash)

def encrypt_credentials(credentials: dict) -> str:
    """Encrypts credential dictionary into a secure token string."""
    if not credentials:
        return ""
    f = Fernet(_get_fernet_key())
    payload = json.dumps(credentials).encode("utf-8")
    return f.encrypt(payload).decode("utf-8")

def decrypt_credentials(encrypted_str: Optional[str]) -> dict:
    """Decrypts secure token string into credential dictionary."""
    if not encrypted_str:
        return {}
    try:
        f = Fernet(_get_fernet_key())
        decrypted = f.decrypt(encrypted_str.encode("utf-8")).decode("utf-8")
        return json.loads(decrypted)
    except Exception:
        try:
            return json.loads(encrypted_str)
        except Exception:
            return {}


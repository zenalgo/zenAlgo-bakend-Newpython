from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    firstName: Optional[str] = Field(None, alias="firstName")
    lastName: Optional[str] = Field(None, alias="lastName")
    referredByCode: Optional[str] = Field(None, alias="referredByCode")

    model_config = {
        "populate_by_name": True
    }

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenRefreshRequest(BaseModel):
    refreshToken: str = Field(..., alias="refreshToken")

    model_config = {
        "populate_by_name": True
    }

class AuthResponse(BaseModel):
    email: str
    role: str
    accessToken: str = Field(..., alias="accessToken")
    refreshToken: str = Field(..., alias="refreshToken")

    model_config = {
        "populate_by_name": True
    }

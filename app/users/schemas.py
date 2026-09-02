from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from app.users.models import UserRole

class UserDto(BaseModel):
    id: int
    email: EmailStr
    role: str
    is_active: bool = Field(..., alias="isActive")
    referral_code: str = Field(..., alias="referralCode")
    referred_by_id: Optional[int] = Field(None, alias="referredById")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")
    first_name: Optional[str] = Field(None, alias="firstName")
    last_name: Optional[str] = Field(None, alias="lastName")

    model_config = {
        "populate_by_name": True,
        "from_attributes": True
    }

class ProvisionUserRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    role: UserRole
    referredByCode: Optional[str] = Field(None, alias="referredByCode")
    firstName: Optional[str] = Field(None, alias="firstName")
    lastName: Optional[str] = Field(None, alias="lastName")

    model_config = {
        "populate_by_name": True
    }

class UserStatusUpdateRequest(BaseModel):
    active: Optional[bool] = None
    isActive: Optional[bool] = Field(None, alias="isActive")

    @property
    def is_active_val(self) -> bool:
        if self.active is not None:
            return self.active
        if self.isActive is not None:
            return self.isActive
        return True

    model_config = {
        "populate_by_name": True
    }

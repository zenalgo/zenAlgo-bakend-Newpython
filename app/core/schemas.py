from pydantic import BaseModel
from typing import Optional, Generic, TypeVar

T = TypeVar('T')

class ApiResponse(BaseModel, Generic[T]):
    success: bool
    code: Optional[str] = None
    message: str
    data: Optional[T] = None
    requestId: Optional[str] = None

    model_config = {
        "populate_by_name": True
    }

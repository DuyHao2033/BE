from uuid import UUID
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    role: str = "issuer"  # 'super_admin' | 'org_admin' | 'issuer'
    organization_id: Optional[UUID] = None


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


class UserRead(BaseModel):
    id: UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    organization_id: Optional[UUID]
    created_at: datetime

    model_config = {"from_attributes": True}

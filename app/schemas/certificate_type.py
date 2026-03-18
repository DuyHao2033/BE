from uuid import UUID
from datetime import datetime
from typing import Optional, Any, List

from pydantic import BaseModel


class CertificateTypeBase(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    field_schema: dict[str, Any] = {}


class CertificateTypeCreate(CertificateTypeBase):
    pass


class CertificateTypeUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    field_schema: Optional[dict[str, Any]] = None


class CertificateTypeRead(CertificateTypeBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CertificateTypeListResponse(BaseModel):
    items: List[CertificateTypeRead]
    total: int
    page: int
    limit: int

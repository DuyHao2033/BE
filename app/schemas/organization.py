from uuid import UUID
from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel


class OrgCreate(BaseModel):
    name: str
    slug: str
    logo_url: Optional[str] = None
    website: Optional[str] = None
    settings: dict[str, Any] = {}


class OrgUpdate(BaseModel):
    name: Optional[str] = None
    logo_url: Optional[str] = None
    website: Optional[str] = None
    settings: Optional[dict[str, Any]] = None


class OrgRead(BaseModel):
    id: UUID
    name: str
    slug: str
    logo_url: Optional[str]
    website: Optional[str]
    settings: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}

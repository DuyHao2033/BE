from uuid import UUID
from datetime import datetime
from typing import Optional, Any, List

from pydantic import BaseModel


class TemplateCreate(BaseModel):
    name: str
    organization_id: Optional[UUID] = None  # Added for super_admin
    description: Optional[str] = None
    category: Optional[str] = None
    page_size: str = "A4"
    orientation: str = "landscape"
    background_url: Optional[str] = None
    layout_json: dict[str, Any] = {}
    custom_fields: list[dict[str, Any]] = []


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    page_size: Optional[str] = None
    orientation: Optional[str] = None
    background_url: Optional[str] = None
    layout_json: Optional[dict[str, Any]] = None
    custom_fields: Optional[list[dict[str, Any]]] = None
    is_active: Optional[bool] = None


class TemplateRead(BaseModel):
    id: UUID
    organization_id: Optional[UUID]
    name: str
    description: Optional[str]
    category: Optional[str]
    page_size: str
    orientation: str
    background_url: Optional[str]
    layout_json: dict[str, Any]
    custom_fields: list[Any]
    is_active: bool
    created_by: Optional[UUID]
    created_at: datetime
    model_config = {"from_attributes": True}


class TemplateAsset(BaseModel):
    url: str
    absolute_path: str


class TemplateListResponse(BaseModel):
    items: List[TemplateRead]
    total: int
    page: int
    limit: int

from uuid import UUID
from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel


class BatchCreate(BaseModel):
    name: str
    description: Optional[str] = None
    template_id: UUID
    decision_id: Optional[UUID] = None
    registry_start_number: Optional[int] = None


class BatchRead(BaseModel):
    id: UUID
    organization_id: UUID
    template_id: UUID
    decision_id: Optional[UUID]
    registry_start_number: Optional[int]
    created_by: Optional[UUID]
    name: str
    description: Optional[str]
    source_file_url: Optional[str]
    total_count: int
    success_count: int
    failed_count: int
    status: str
    error_log: list[Any]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}

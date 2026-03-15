from uuid import UUID
from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel, EmailStr


class CertIssueRequest(BaseModel):
    template_id: UUID
    recipient_name: str
    recipient_email: Optional[EmailStr] = None
    recipient_id: Optional[str] = None  # student ID / employee ID
    title: str
    custom_data: dict[str, Any] = {}
    expires_at: Optional[datetime] = None
    issued_at: Optional[datetime] = None  # defaults to now if not provided
    batch_id: Optional[UUID] = None
    organization_id: Optional[UUID] = None


class CertRevokeRequest(BaseModel):
    reason: str


class CertReplaceRequest(BaseModel):
    reason: str
    # New certificate data (same fields as issue)
    recipient_name: Optional[str] = None
    recipient_email: Optional[str] = None
    title: Optional[str] = None
    custom_data: Optional[dict[str, Any]] = None
    expires_at: Optional[datetime] = None


class CertRead(BaseModel):
    id: UUID
    cert_code: str
    template_id: UUID
    organization_id: UUID
    issued_by: Optional[UUID]
    recipient_name: str
    recipient_email: Optional[str]
    recipient_id: Optional[str]
    title: str
    custom_data: dict[str, Any]
    status: str
    revoked_at: Optional[datetime]
    revoked_reason: Optional[str]
    replaced_by: Optional[UUID]
    expires_at: Optional[datetime]
    pdf_url: Optional[str]
    batch_id: Optional[UUID]
    issued_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}

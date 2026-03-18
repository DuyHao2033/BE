from uuid import UUID
from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel


class CertificateTypeSummary(BaseModel):
    id: UUID
    code: str
    name: str
    description: Optional[str] = None
    field_schema: dict[str, Any] = {}

    model_config = {"from_attributes": True}


class DecisionSummary(BaseModel):
    id: UUID
    decision_number: str
    decision_date: datetime
    title: Optional[str] = None

    model_config = {"from_attributes": True}


class VerifyResult(BaseModel):
    is_valid: bool
    cert_code: str
    status: str  # 'active' | 'revoked' | 'expired' | 'replaced'
    recipient_name: str
    title: str
    organization_name: str
    issued_at: datetime
    expires_at: Optional[datetime]
    revoked_at: Optional[datetime]
    revoked_reason: Optional[str]
    replaced_by: Optional[UUID]
    cert_id: Optional[UUID]
    pdf_url: Optional[str] = None
    certificate_type: Optional[CertificateTypeSummary] = None
    decision: Optional[DecisionSummary] = None
    custom_data: dict[str, Any] = {}

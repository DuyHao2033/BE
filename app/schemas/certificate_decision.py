from uuid import UUID
from datetime import date, datetime
from typing import Optional, List

from pydantic import BaseModel


class CertificateDecisionBase(BaseModel):
    decision_number: str
    decision_date: date
    title: Optional[str] = None


class CertificateDecisionCreate(CertificateDecisionBase):
    pass


class CertificateDecisionUpdate(BaseModel):
    decision_number: Optional[str] = None
    decision_date: Optional[date] = None
    title: Optional[str] = None


class CertificateDecisionRead(CertificateDecisionBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CertificateDecisionListResponse(BaseModel):
    items: List[CertificateDecisionRead]
    total: int
    page: int
    limit: int

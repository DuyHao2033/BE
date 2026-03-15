from uuid import UUID
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


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

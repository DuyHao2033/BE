"""
Log Service — writes events to certificate_logs table.
"""
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.certificate_log import CertificateLog


class EventType:
    ISSUED = "issued"
    REVOKED = "revoked"
    REPLACED = "replaced"
    VERIFIED = "verified"
    PDF_DOWNLOADED = "pdf_downloaded"
    BATCH_ISSUED = "batch_issued"


def log_event(
    db: Session,
    certificate_id: UUID,
    event_type: str,
    actor_id: Optional[UUID] = None,
    actor_ip: Optional[str] = None,
    actor_ua: Optional[str] = None,
    extra_metadata: Optional[dict] = None,
) -> CertificateLog:
    entry = CertificateLog(
        certificate_id=certificate_id,
        event_type=event_type,
        actor_id=actor_id,
        actor_ip=actor_ip,
        actor_ua=actor_ua,
        extra_metadata=extra_metadata or {},
        created_at=datetime.now(timezone.utc),
    )
    db.add(entry)
    db.flush()
    return entry

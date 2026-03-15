"""Public verification endpoint — no authentication required."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.models.certificate import Certificate
from app.models.organization import Organization
from app.models.verify_session import VerifySession
from app.schemas.verify import VerifyResult
from app.services import log_service

router = APIRouter(prefix="/verify", tags=["Verify (Public)"])


@router.get("/{cert_code}", response_model=VerifyResult)
def verify_certificate(
    cert_code: str,
    request: Request,
    db: Session = Depends(get_db),
):
    cert: Certificate | None = db.query(Certificate).filter(
        Certificate.cert_code == cert_code.upper()
    ).first()

    viewer_ip = request.client.host if request.client else None
    viewer_ua = request.headers.get("user-agent")

    is_valid = cert is not None and cert.status == "active"

    # Log verify session regardless of outcome
    session = VerifySession(
        certificate_id=cert.id if cert else None,
        cert_code=cert_code.upper(),
        is_valid=is_valid,
        viewer_ip=viewer_ip,
        viewer_ua=viewer_ua,
        created_at=datetime.now(timezone.utc),
    )
    db.add(session)

    if cert:
        log_service.log_event(
            db=db,
            certificate_id=cert.id,
            event_type=log_service.EventType.VERIFIED,
            actor_ip=viewer_ip,
            actor_ua=viewer_ua,
            extra_metadata={"is_valid": is_valid, "status": cert.status},
        )

    db.commit()

    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not found")

    org = db.query(Organization).filter(Organization.id == cert.organization_id).first()
    org_name = org.name if org else "Unknown"

    # Check if expired
    effective_status = cert.status
    if effective_status == "active" and cert.expires_at:
        if cert.expires_at < datetime.now(timezone.utc):
            effective_status = "expired"
            is_valid = False

    return VerifyResult(
        is_valid=is_valid,
        cert_code=cert.cert_code,
        status=effective_status,
        recipient_name=cert.recipient_name,
        title=cert.title,
        organization_name=org_name,
        issued_at=cert.issued_at,
        expires_at=cert.expires_at,
        revoked_at=cert.revoked_at,
        revoked_reason=cert.revoked_reason,
        replaced_by=cert.replaced_by,
        cert_id=cert.id,
    )

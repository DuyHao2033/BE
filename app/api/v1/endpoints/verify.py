"""Public verification endpoint — no authentication required."""
from datetime import datetime, timezone
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_db
from app.models.certificate import Certificate
from app.models.organization import Organization
from app.models.verify_session import VerifySession
from app.schemas.verify import VerifyResult
from app.services import log_service
from app.services.storage_service import get_absolute_path

router = APIRouter(prefix="/verify", tags=["Verify (Public)"])


def _resolve_public_pdf_path(cert: Certificate) -> str:
    if not cert.pdf_url:
        raise HTTPException(status_code=404, detail="PDF not yet generated")

    abs_path = get_absolute_path(cert.pdf_url)
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="PDF file not found on disk")
    return abs_path


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
    cert_type = None
    if cert.template and cert.template.certificate_type:
        cert_type = cert.template.certificate_type

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
        pdf_url=f"{settings.PUBLIC_BASE_URL.rstrip('/')}/api/v1/verify/{cert.cert_code}/pdf",
        certificate_type=cert_type,
        decision=cert.decision,
        custom_data=cert.custom_data or {},
    )


@router.get("/{cert_code}/pdf")
def verify_certificate_pdf(
    cert_code: str,
    request: Request,
    db: Session = Depends(get_db),
):
    cert: Certificate | None = db.query(Certificate).filter(
        Certificate.cert_code == cert_code.upper()
    ).first()

    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not found")

    # Only expose the PDF for valid, non-expired, non-revoked certificates.
    effective_status = cert.status
    is_valid = cert.status == "active"
    if effective_status == "active" and cert.expires_at and cert.expires_at < datetime.now(timezone.utc):
        effective_status = "expired"
        is_valid = False

    if effective_status != "active" or not is_valid:
        raise HTTPException(status_code=403, detail="Certificate is not eligible for public PDF preview")

    abs_path = _resolve_public_pdf_path(cert)

    viewer_ip = request.client.host if request.client else None
    viewer_ua = request.headers.get("user-agent")
    log_service.log_event(
        db=db,
        certificate_id=cert.id,
        event_type=log_service.EventType.PDF_DOWNLOADED,
        actor_ip=viewer_ip,
        actor_ua=viewer_ua,
        extra_metadata={"public": True, "cert_code": cert.cert_code},
    )
    db.commit()

    filename = f"certificate_{cert.cert_code}.pdf"
    return FileResponse(
        abs_path,
        media_type="application/pdf",
        filename=filename,
        content_disposition_type="inline",
    )

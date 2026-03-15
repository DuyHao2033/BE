"""Certificate endpoints — issue, list, detail, revoke, replace, download PDF."""
import os
from uuid import UUID
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user, require_roles
from app.models.certificate import Certificate
from app.models.organization import Organization
from app.models.user import User
from app.models.template import Template
from app.schemas.certificate import CertIssueRequest, CertRead, CertRevokeRequest, CertReplaceRequest
from app.services.certificate_service import issue_certificate
from app.services import log_service
from app.core.config import settings

router = APIRouter(prefix="/certificates", tags=["Certificates"])


def _get_user_org(db: Session, current_user: User) -> Organization:
    org = db.query(Organization).filter(Organization.id == current_user.organization_id).first()
    if not org:
        raise HTTPException(status_code=400, detail="User has no associated organization")
    return org


def _get_cert_or_404(cert_id: UUID, db: Session) -> Certificate:
    cert = db.query(Certificate).filter(Certificate.id == cert_id).first()
    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not found")
    return cert


@router.post("", response_model=CertRead, status_code=status.HTTP_201_CREATED)
def issue_single_certificate(
    payload: CertIssueRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("super_admin", "org_admin", "issuer")),
):
    # Determine the organization for issuance
    org = None
    
    # 1. If organization_id is in payload (allowed for super_admin)
    if payload.organization_id and current_user.role == "super_admin":
        org = db.query(Organization).filter(Organization.id == payload.organization_id).first()
        if not org:
            raise HTTPException(status_code=404, detail="Organization specified in payload not found")
            
    # 2. Use user's own organization
    if not org and current_user.organization_id:
        org = db.query(Organization).filter(Organization.id == current_user.organization_id).first()
    
    # 3. Use the template's organization
    if not org:
        template = db.query(Template).filter(Template.id == payload.template_id).first()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        if template.organization_id:
            org = db.query(Organization).filter(Organization.id == template.organization_id).first()
            
    if not org:
        # If still no org, just take the first organization in the system for super_admin as a final fallback
        if current_user.role == "super_admin":
            org = db.query(Organization).first()
            
    if not org:
        raise HTTPException(status_code=400, detail="User has no associated organization and template has no organization context")

    actor_ip = request.client.host if request.client else None
    actor_ua = request.headers.get("user-agent")

    try:
        cert = issue_certificate(
            db=db,
            payload=payload,
            organization=org,
            issued_by_id=current_user.id,
            actor_ip=actor_ip,
            actor_ua=actor_ua,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return cert


@router.get("", response_model=List[CertRead])
def list_certificates(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("super_admin", "org_admin", "issuer")),
    status_filter: Optional[str] = Query(None, alias="status"),
    batch_id: Optional[UUID] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    q = db.query(Certificate)
    if current_user.role != "super_admin":
        q = q.filter(Certificate.organization_id == current_user.organization_id)
    if status_filter:
        q = q.filter(Certificate.status == status_filter)
    if batch_id:
        q = q.filter(Certificate.batch_id == batch_id)

    q = q.order_by(Certificate.issued_at.desc())
    return q.offset(skip).limit(limit).all()


@router.get("/{cert_id}", response_model=CertRead)
def get_certificate(
    cert_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("super_admin", "org_admin", "issuer")),
):
    cert = _get_cert_or_404(cert_id, db)
    if current_user.role != "super_admin" and cert.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return cert


@router.post("/{cert_id}/revoke", response_model=CertRead)
def revoke_certificate(
    cert_id: UUID,
    payload: CertRevokeRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("super_admin", "org_admin")),
):
    cert = _get_cert_or_404(cert_id, db)
    if current_user.role != "super_admin" and cert.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Access denied")

    if cert.status == "revoked":
        raise HTTPException(status_code=400, detail="Certificate is already revoked")

    cert.status = "revoked"
    cert.revoked_at = datetime.now(timezone.utc)
    cert.revoked_reason = payload.reason

    log_service.log_event(
        db=db,
        certificate_id=cert.id,
        event_type=log_service.EventType.REVOKED,
        actor_id=current_user.id,
        actor_ip=request.client.host if request.client else None,
        extra_metadata={"reason": payload.reason},
    )

    db.commit()
    db.refresh(cert)
    return cert


@router.post("/{cert_id}/replace", response_model=CertRead, status_code=status.HTTP_201_CREATED)
def replace_certificate(
    cert_id: UUID,
    payload: CertReplaceRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("super_admin", "org_admin")),
):
    old_cert = _get_cert_or_404(cert_id, db)
    if current_user.role != "super_admin" and old_cert.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Determine the organization for replacement
    org = None
    if current_user.organization_id:
        org = db.query(Organization).filter(Organization.id == current_user.organization_id).first()
    
    if not org and current_user.role == "super_admin":
        if old_cert.organization_id:
            org = db.query(Organization).filter(Organization.id == old_cert.organization_id).first()
            
    if not org:
        raise HTTPException(status_code=400, detail="Organization context not found for replacement")
    actor_ip = request.client.host if request.client else None
    actor_ua = request.headers.get("user-agent")

    # Issue new certificate with updated data
    new_payload = CertIssueRequest(
        template_id=old_cert.template_id,
        recipient_name=payload.recipient_name or old_cert.recipient_name,
        recipient_email=payload.recipient_email or old_cert.recipient_email,
        recipient_id=old_cert.recipient_id,
        title=payload.title or old_cert.title,
        custom_data=payload.custom_data if payload.custom_data is not None else old_cert.custom_data,
        expires_at=payload.expires_at or old_cert.expires_at,
    )

    try:
        new_cert = issue_certificate(
            db=db,
            payload=new_payload,
            organization=org,
            issued_by_id=current_user.id,
            actor_ip=actor_ip,
            actor_ua=actor_ua,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Mark old cert as replaced
    old_cert.status = "replaced"
    old_cert.revoked_at = datetime.now(timezone.utc)
    old_cert.revoked_reason = payload.reason
    old_cert.replaced_by = new_cert.id

    log_service.log_event(
        db=db,
        certificate_id=old_cert.id,
        event_type=log_service.EventType.REPLACED,
        actor_id=current_user.id,
        actor_ip=actor_ip,
        extra_metadata={"replaced_by": str(new_cert.id), "reason": payload.reason},
    )

    db.commit()
    db.refresh(new_cert)
    return new_cert


@router.get("/{cert_id}/pdf")
def download_pdf(
    cert_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cert = _get_cert_or_404(cert_id, db)
    if current_user.role != "super_admin" and cert.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Access denied")

    if not cert.pdf_url:
        raise HTTPException(status_code=404, detail="PDF not yet generated")

    # pdf_url is like /uploads/pdf/<org_slug>/<id>.pdf
    # Map to filesytem
    rel = cert.pdf_url.lstrip("/")
    # UPLOAD_DIR might be ./uploads — strip leading ./
    upload_base = settings.UPLOAD_DIR.lstrip("./").lstrip("/")
    abs_path = os.path.join(upload_base, rel.removeprefix("uploads/"))

    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="PDF file not found on disk")

    log_service.log_event(
        db=db,
        certificate_id=cert.id,
        event_type=log_service.EventType.PDF_DOWNLOADED,
        actor_id=current_user.id,
        actor_ip=request.client.host if request.client else None,
    )
    db.commit()

    filename = f"certificate_{cert.cert_code}.pdf"
    return FileResponse(
        abs_path,
        media_type="application/pdf",
        filename=filename,
    )

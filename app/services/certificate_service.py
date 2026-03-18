"""
Certificate issuance core service.
Shared logic used by both single-issue and batch-issue endpoints.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.certificate import Certificate
from app.models.template import Template
from app.models.organization import Organization
from app.schemas.certificate import CertIssueRequest
from app.services import cert_code as cert_code_svc
from app.services import qr_service, pdf_service
from app.services import storage_service, log_service


def _build_cert_data(cert: Certificate) -> dict:
    """Flatten certificate fields into a dict for PDF rendering."""
    data = {
        "cert_code": cert.cert_code,
        "recipient_name": cert.recipient_name,
        "recipient_email": cert.recipient_email or "",
        "recipient_id": cert.recipient_id or "",
        "title": cert.title,
        "issued_at": cert.issued_at.strftime("%d/%m/%Y"),
        "expires_at": cert.expires_at.strftime("%d/%m/%Y") if cert.expires_at else "",
        "custom_data": cert.custom_data,
        "registry_number": cert.registry_number or "",
        # Dynamic placeholders support
        "certificate": {
            "serial": cert.cert_code,
            "registry_number": cert.registry_number or "",
        }
    }
    
    if cert.decision:
        data["decision_number"] = cert.decision.decision_number
        data["decision_date"] = cert.decision.decision_date.strftime("%d/%m/%Y")
        data["decision"] = {
            "number": cert.decision.decision_number,
            "date": cert.decision.decision_date.strftime("%d/%m/%Y"),
        }
    else:
        data["decision_number"] = ""
        data["decision_date"] = ""
        data["decision"] = {
            "number": "",
            "date": "",
        }
    
    # Merge custom_data into top-level for easier access
    # We allow custom_data to override standard fields to give users full control over display values (e.g. custom date strings)
    if cert.custom_data:
        for k, v in cert.custom_data.items():
            data[k] = v
        
    return data


def issue_certificate(
    db: Session,
    payload: CertIssueRequest,
    organization: Organization,
    issued_by_id: Optional[uuid.UUID] = None,
    actor_ip: Optional[str] = None,
    actor_ua: Optional[str] = None,
    batch_id: Optional[uuid.UUID] = None,
) -> Certificate:
    """
    Core issuance logic:
    1. Generate cert_code (retry on collision)
    2. Create Certificate db record
    3. Generate QR code PNG → save
    4. Render PDF → save
    5. Update pdf_url
    6. Write audit log
    7. Commit & return
    """
    template: Template = db.query(Template).filter(
        Template.id == payload.template_id,
        Template.is_active == True,
    ).first()
    if template is None:
        raise ValueError(f"Template {payload.template_id} not found or inactive")

    # 1. Generate unique cert_code
    for _ in range(10):
        code = cert_code_svc.generate_cert_code()
        exists = db.query(Certificate).filter(Certificate.cert_code == code).first()
        if not exists:
            break
    else:
        raise RuntimeError("Could not generate a unique cert_code after 10 attempts")

    issued_at = payload.issued_at or datetime.now(timezone.utc)

    # 2. Create DB record
    cert = Certificate(
        cert_code=code,
        template_id=template.id,
        organization_id=organization.id,
        issued_by=issued_by_id,
        recipient_name=payload.recipient_name,
        recipient_email=payload.recipient_email,
        recipient_id=payload.recipient_id,
        title=payload.title,
        custom_data=payload.custom_data,
        expires_at=payload.expires_at,
        issued_at=issued_at,
        batch_id=batch_id,
        decision_id=payload.decision_id,
        registry_number=payload.registry_number,
        status="active",
    )
    db.add(cert)
    db.flush()  # get cert.id

    # 3. Generate QR code PNG
    qr_bytes = qr_service.generate_qr_bytes(code)
    qr_url = storage_service.save_bytes(qr_bytes, f"qr/{organization.slug}", f"{cert.id}.png")

    # 4. Render PDF
    cert_data = _build_cert_data(cert)
    pdf_bytes = pdf_service.render_certificate_pdf(
        layout_json=template.layout_json,
        page_size=template.page_size,
        orientation=template.orientation,
        background_url=template.background_url,
        cert_data=cert_data,
        qr_bytes=qr_bytes,
    )
    pdf_url = storage_service.save_bytes(pdf_bytes, f"pdf/{organization.slug}", f"{cert.id}.pdf")

    # 5. Update pdf_url
    cert.pdf_url = pdf_url
    db.flush()

    # 6. Audit log
    log_service.log_event(
        db=db,
        certificate_id=cert.id,
        event_type=log_service.EventType.ISSUED,
        actor_id=issued_by_id,
        actor_ip=actor_ip,
        actor_ua=actor_ua,
        extra_metadata={"cert_code": code, "recipient": cert.recipient_name},
    )

    db.commit()
    db.refresh(cert)
    return cert

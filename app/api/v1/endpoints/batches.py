"""Batch issuance endpoints."""
from uuid import UUID
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, Request, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_roles
from app.models.certificate import Certificate
from app.models.certificate_batch import CertificateBatch
from app.models.organization import Organization
from app.models.user import User
from app.models.template import Template
from app.schemas.batch import BatchRead
from app.schemas.certificate import CertRead
from app.services.batch_service import process_batch_task
from app.services.storage_service import save_upload

router = APIRouter(prefix="/batches", tags=["Batches"])

ALLOWED_FILE_TYPES = {
    "text/csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "application/octet-stream",  # sometimes Excel uploads as this
}


def _get_user_org(db: Session, current_user: User) -> Organization:
    org = db.query(Organization).filter(Organization.id == current_user.organization_id).first()
    if not org:
        raise HTTPException(status_code=400, detail="User has no associated organization")
    return org


@router.post("", response_model=BatchRead, status_code=status.HTTP_202_ACCEPTED)
async def create_batch(
    background_tasks: BackgroundTasks,
    request: Request,
    file: UploadFile = File(...),
    name: str = Form(...),
    template_id: UUID = Form(...),
    decision_id: UUID = Form(None),
    registry_start_number: int = Form(None),
    description: str = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("super_admin", "org_admin", "issuer")),
):
    # Determine the organization
    org = None
    if current_user.organization_id:
        org = db.query(Organization).filter(Organization.id == current_user.organization_id).first()
    
    if not org and current_user.role == "super_admin":
        template = db.query(Template).filter(Template.id == template_id).first()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        if template.organization_id:
            org = db.query(Organization).filter(Organization.id == template.organization_id).first()

    if not org and current_user.role == "super_admin":
        org = db.query(Organization).first()

    if not org:
        raise HTTPException(status_code=400, detail="User has no associated organization and no template context found")
    actor_ip = request.client.host if request.client else None

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    # Save source file
    source_url = save_upload(content, f"batch_sources/{org.slug}", file.filename or "batch.csv")

    batch = CertificateBatch(
        organization_id=org.id,
        template_id=template_id,
        created_by=current_user.id,
        name=name,
        description=description,
        source_file_url=source_url,
        decision_id=decision_id,
        registry_start_number=registry_start_number,
        total_count=0,
        success_count=0,
        failed_count=0,
        status="pending",
        error_log=[],
        created_at=datetime.now(timezone.utc),
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)

    # Run batch processing as background task
    background_tasks.add_task(
        process_batch_task,
        batch_id=batch.id,
        file_content=content,
        filename=file.filename or "batch.csv",
        organization_id=org.id,
        issued_by_id=current_user.id,
        actor_ip=actor_ip,
    )

    return batch


@router.get("", response_model=List[BatchRead])
def list_batches(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("super_admin", "org_admin", "issuer")),
    skip: int = 0,
    limit: int = 50,
):
    q = db.query(CertificateBatch)
    if current_user.role != "super_admin":
        q = q.filter(CertificateBatch.organization_id == current_user.organization_id)
    return q.order_by(CertificateBatch.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/{batch_id}", response_model=BatchRead)
def get_batch(
    batch_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("super_admin", "org_admin", "issuer")),
):
    batch = db.query(CertificateBatch).filter(CertificateBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    if current_user.role != "super_admin" and batch.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return batch


@router.get("/{batch_id}/certificates", response_model=list[CertRead])
def list_batch_certificates(
    batch_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("super_admin", "org_admin", "issuer")),
    skip: int = 0,
    limit: int = 50,
):
    batch = db.query(CertificateBatch).filter(CertificateBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    if current_user.role != "super_admin" and batch.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Access denied")

    q = db.query(Certificate).filter(Certificate.batch_id == batch_id)
    q = q.order_by(Certificate.issued_at.desc())
    return q.offset(skip).limit(limit).all()


@router.get("/templates/{template_id}/excel-template")
def download_excel_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("super_admin", "org_admin", "issuer")),
):
    """Generate and download an Excel template based on the certificate template fields."""
    template = db.query(Template).filter(Template.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    if current_user.role != "super_admin" and template.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Access denied")

    import openpyxl
    from io import BytesIO
    from fastapi.responses import StreamingResponse
    import re
    from urllib.parse import quote

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Batch Issue Template"

    # Core system fields
    headers = ["recipient_name", "recipient_email", "recipient_id", "title", "expires_at", "registry_number"]
    
    # Extract placeholders from layout_json
    placeholders = set()
    layout = template.layout_json
    if isinstance(layout, dict) and isinstance(layout.get("elements"), list):
        for el in layout["elements"]:
            if isinstance(el, dict) and el.get("type") == "text" and el.get("content"):
                content = el["content"]
                # Find matches for {{field}}
                matches = re.findall(r"\{\{([^{}]+)\}\}", content)
                for m in matches:
                    field = m.strip()
                    # Skip system fields that are already in headers or special ones
                    if field in ["recipient_name", "recipient_email", "recipient_id", "title", "issued_at", "expires_at"]:
                        continue
                    if field.startswith("decision.") or field == "certificate.registry_number" or field == "certificate.serial":
                        continue
                    placeholders.add(field)

    # Also add fields explicitly defined in template.custom_fields
    if isinstance(template.custom_fields, list):
        for f in template.custom_fields:
            if isinstance(f, str):
                placeholders.add(f)
            elif isinstance(f, dict) and f.get("key"):
                placeholders.add(f["key"])

    # Add custom fields from elements (prefixed with custom_)
    for ph in sorted(list(placeholders)):
        headers.append(f"custom_{ph}")

    ws.append(headers)
    
    # Add a sample row (optional)
    # ws.append(["Nguyen Van A", "a@example.com", "ID123", "Chứng nhận hoàn thành", "2025-12-31", "", ""])

    # Auto-adjust column width
    for i, column_cells in enumerate(ws.columns, start=1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = 20

    out = BytesIO()
    wb.save(out)
    out.seek(0)

    # Proper header encoding for non-ASCII filenames (RFC 5987)
    ascii_filename = "".join(c for c in template.name if ord(c) < 128).replace(' ', '_')
    if not ascii_filename:
        ascii_filename = "template"
    ascii_filename = f"{ascii_filename}.xlsx"
    
    encoded_filename = quote(f"template_{template.name.replace(' ', '_')}.xlsx")
    
    return StreamingResponse(
        out,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{ascii_filename}"; filename*=UTF-8\'\'{encoded_filename}'
        }
    )

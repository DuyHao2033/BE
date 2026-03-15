"""Batch issuance endpoints."""
from uuid import UUID
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, Request, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_roles
from app.models.certificate_batch import CertificateBatch
from app.models.organization import Organization
from app.models.user import User
from app.models.template import Template
from app.schemas.batch import BatchRead
from app.services.batch_service import process_batch
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
        process_batch,
        db=db,
        batch=batch,
        file_content=content,
        filename=file.filename or "batch.csv",
        organization=org,
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

"""Organization endpoints."""
from uuid import UUID
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_roles
from app.models.organization import Organization
from app.models.user import User
from app.schemas.organization import OrgCreate, OrgRead, OrgUpdate
from app.services.storage_service import save_upload, get_absolute_path

router = APIRouter(prefix="/organizations", tags=["Organizations"])

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


@router.get("", response_model=List[OrgRead])
def list_organizations(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("super_admin")),
):
    return db.query(Organization).all()


@router.post("", response_model=OrgRead, status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: OrgCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("super_admin")),
):
    existing = db.query(Organization).filter(Organization.slug == payload.slug).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Slug '{payload.slug}' already exists")

    org = Organization(**payload.model_dump())
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


@router.get("/{org_id}", response_model=OrgRead)
def get_organization(
    org_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("super_admin", "org_admin", "issuer")),
):
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # org_admin and issuer can only view their own org
    if current_user.role != "super_admin" and current_user.organization_id != org_id:
        raise HTTPException(status_code=403, detail="Access denied")

    return org


@router.patch("/{org_id}", response_model=OrgRead)
def update_organization(
    org_id: UUID,
    payload: OrgUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("super_admin")),
):
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(org, field, value)

    db.commit()
    db.refresh(org)
    return org


@router.delete("/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_organization(
    org_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("super_admin")),
):
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # This will cascade delete based on DB configuration or needs manual handling
    # For now, let's assume standard delete
    db.delete(org)
    db.commit()


@router.post("/{org_id}/logo", response_model=OrgRead)
async def upload_logo(
    org_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("super_admin", "org_admin")),
):
    """
    Upload a logo for an organization.
    """
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # org_admin can only upload logo for their own org
    if current_user.role != "super_admin" and current_user.organization_id != org_id:
        raise HTTPException(status_code=403, detail="Access denied")

    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail=f"Only JPEG/PNG/WEBP supported, got {file.content_type}")

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:  # 5 MB limit
        raise HTTPException(status_code=400, detail="File too large (max 5 MB)")

    # Save to organization-specific folder
    url = save_upload(content, f"orgs/{org.slug}", file.filename or "logo.png")
    
    # Store the URL in the database
    org.logo_url = url

    db.commit()
    db.refresh(org)
    return org

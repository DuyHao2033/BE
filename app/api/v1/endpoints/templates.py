"""Template management endpoints."""
import os
from uuid import UUID
from typing import List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user, require_roles
from app.models.template import Template
from app.models.user import User
from app.schemas.template import TemplateCreate, TemplateRead, TemplateUpdate, TemplateAsset, TemplateListResponse
from app.services.storage_service import save_upload, get_absolute_path

router = APIRouter(prefix="/templates", tags=["Templates"])

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


def _get_template_or_404(template_id: UUID, db: Session) -> Template:
    tmpl = db.query(Template).filter(Template.id == template_id).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    return tmpl


@router.get("", response_model=Union[TemplateListResponse, List[TemplateRead]])
def list_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("super_admin", "org_admin", "issuer")),
    q: Optional[str] = None,
    page: int = 1,
    limit: int = 100,
):
    query = db.query(Template)
    if current_user.role != "super_admin":
        # Regular users see templates from their organization AND global templates
        query = query.filter(
            or_(
                Template.organization_id == current_user.organization_id,
                Template.organization_id == None
            )
        )
    
    if q:
        query = query.filter(
            or_(
                Template.name.ilike(f"%{q}%"),
                Template.category.ilike(f"%{q}%"),
                Template.description.ilike(f"%{q}%")
            )
        )
    
    # If not a list request for builder/issuance, we might want to show all.
    # For now, let's keep it simple: admins see everything, issuers see only active?
    # Actually, the user wants a management screen, so we should show all if managed.
    # If it's a simple list request (old frontend code), we might want to maintain compatibility.
    
    total = query.count()
    items = query.order_by(Template.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit
    }


@router.post("", response_model=TemplateRead, status_code=status.HTTP_201_CREATED)
def create_template(
    payload: TemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("super_admin", "org_admin")),
):
    org_id = payload.organization_id
    if current_user.role == "org_admin":
        # org_admin always creates templates for their own organization
        org_id = current_user.organization_id
    elif current_user.role == "super_admin" and not org_id:
        # super_admin can create templates for their own organization, or leave it None for a global template
        org_id = current_user.organization_id

    # If it's an org_admin but they somehow don't have an org_id, that's an error
    if current_user.role == "org_admin" and not org_id:
        raise HTTPException(status_code=400, detail="org_admin must belong to an organization")

    template_data = payload.model_dump()
    template_data.pop("organization_id", None)

    tmpl = Template(
        organization_id=org_id,
        created_by=current_user.id,
        **template_data,
    )
    db.add(tmpl)
    db.commit()
    db.refresh(tmpl)
    return tmpl


@router.get("/{template_id}", response_model=TemplateRead)
def get_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("super_admin", "org_admin", "issuer")),
):
    tmpl = _get_template_or_404(template_id, db)
    if current_user.role != "super_admin" and tmpl.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return tmpl


@router.patch("/{template_id}", response_model=TemplateRead)
def update_template(
    template_id: UUID,
    payload: TemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("super_admin", "org_admin")),
):
    tmpl = _get_template_or_404(template_id, db)
    if current_user.role != "super_admin" and tmpl.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Access denied")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(tmpl, field, value)

    db.commit()
    db.refresh(tmpl)
    return tmpl


@router.post("/{template_id}/background", response_model=TemplateRead)
async def upload_background(
    template_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("super_admin", "org_admin")),
):
    tmpl = _get_template_or_404(template_id, db)
    if current_user.role != "super_admin" and tmpl.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Access denied")

    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail=f"Only JPEG/PNG/WEBP supported, got {file.content_type}")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10 MB limit
        raise HTTPException(status_code=400, detail="File too large (max 10 MB)")

    url = save_upload(content, "backgrounds", file.filename or "bg.png")

    # Store relative URL so frontend can access it via HTTP
    tmpl.background_url = url

    db.commit()
    db.refresh(tmpl)
    return tmpl


@router.post("/{template_id}/assets", response_model=TemplateAsset)
async def upload_asset(
    template_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("super_admin", "org_admin")),
):
    """
    Upload an image asset (logo, seal, etc.) for use in a template.
    Returns the relative URL and absolute path.
    """
    tmpl = _get_template_or_404(template_id, db)
    if current_user.role != "super_admin" and tmpl.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Access denied")

    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail=f"Only JPEG/PNG/WEBP supported, got {file.content_type}")

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:  # 5 MB limit
        raise HTTPException(status_code=400, detail="File too large (max 5 MB)")

    # Save to a template-specific folder
    url = save_upload(content, f"templates/{template_id}/assets", file.filename or "asset.png")
    abs_path = get_absolute_path(url)

    return TemplateAsset(url=url, absolute_path=abs_path)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("super_admin", "org_admin")),
):
    tmpl = _get_template_or_404(template_id, db)
    if current_user.role != "super_admin" and tmpl.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Access denied")

    db.delete(tmpl)
    db.commit()
    return None

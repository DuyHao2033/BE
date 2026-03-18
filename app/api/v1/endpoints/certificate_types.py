from uuid import UUID
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_roles
from app.models.certificate_type import CertificateType
from app.schemas.certificate_type import CertificateTypeCreate, CertificateTypeRead, CertificateTypeUpdate, CertificateTypeListResponse


router = APIRouter(prefix="/certificate-types", tags=["Certificate Types"])


@router.get("", response_model=CertificateTypeListResponse)
def list_certificate_types(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=100),
):
    query = db.query(CertificateType)
    total = query.count()
    items = query.order_by(CertificateType.name).offset((page - 1) * limit).limit(limit).all()
    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit
    }


@router.post("", response_model=CertificateTypeRead, status_code=status.HTTP_201_CREATED)
def create_certificate_type(
    payload: CertificateTypeCreate,
    db: Session = Depends(get_db),
    _ = Depends(require_roles("super_admin")),
):
    exists = db.query(CertificateType).filter(CertificateType.code == payload.code).first()
    if exists:
        raise HTTPException(status_code=400, detail="Certificate type code already exists")

    new_type = CertificateType(**payload.model_dump())
    db.add(new_type)
    db.commit()
    db.refresh(new_type)
    return new_type


@router.get("/{type_id}", response_model=CertificateTypeRead)
def get_certificate_type(
    type_id: UUID,
    db: Session = Depends(get_db),
):
    cert_type = db.query(CertificateType).filter(CertificateType.id == type_id).first()
    if not cert_type:
        raise HTTPException(status_code=404, detail="Certificate type not found")
    return cert_type


@router.patch("/{type_id}", response_model=CertificateTypeRead)
def update_certificate_type(
    type_id: UUID,
    payload: CertificateTypeUpdate,
    db: Session = Depends(get_db),
    _ = Depends(require_roles("super_admin")),
):
    cert_type = db.query(CertificateType).filter(CertificateType.id == type_id).first()
    if not cert_type:
        raise HTTPException(status_code=404, detail="Certificate type not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(cert_type, field, value)

    db.commit()
    db.refresh(cert_type)
    return cert_type


@router.delete("/{type_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_certificate_type(
    type_id: UUID,
    db: Session = Depends(get_db),
    _ = Depends(require_roles("super_admin")),
):
    cert_type = db.query(CertificateType).filter(CertificateType.id == type_id).first()
    if not cert_type:
        raise HTTPException(status_code=404, detail="Certificate type not found")

    db.delete(cert_type)
    db.commit()
    return None

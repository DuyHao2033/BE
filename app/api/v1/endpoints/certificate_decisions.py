from uuid import UUID
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_roles
from app.models.certificate_decision import CertificateDecision
from app.schemas.certificate_decision import CertificateDecisionCreate, CertificateDecisionRead, CertificateDecisionUpdate, CertificateDecisionListResponse


router = APIRouter(prefix="/certificate-decisions", tags=["Certificate Decisions"])


@router.get("", response_model=CertificateDecisionListResponse)
def list_certificate_decisions(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=100),
):
    query = db.query(CertificateDecision)
    total = query.count()
    items = query.order_by(CertificateDecision.decision_date.desc()).offset((page - 1) * limit).limit(limit).all()
    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit
    }


@router.post("", response_model=CertificateDecisionRead, status_code=status.HTTP_201_CREATED)
def create_certificate_decision(
    payload: CertificateDecisionCreate,
    db: Session = Depends(get_db),
    _ = Depends(require_roles("super_admin", "org_admin")),
):
    new_decision = CertificateDecision(**payload.model_dump())
    db.add(new_decision)
    db.commit()
    db.refresh(new_decision)
    return new_decision


@router.get("/{decision_id}", response_model=CertificateDecisionRead)
def get_certificate_decision(
    decision_id: UUID,
    db: Session = Depends(get_db),
):
    decision = db.query(CertificateDecision).filter(CertificateDecision.id == decision_id).first()
    if not decision:
        raise HTTPException(status_code=404, detail="Certificate decision not found")
    return decision


@router.patch("/{decision_id}", response_model=CertificateDecisionRead)
def update_certificate_decision(
    decision_id: UUID,
    payload: CertificateDecisionUpdate,
    db: Session = Depends(get_db),
    _ = Depends(require_roles("super_admin", "org_admin")),
):
    decision = db.query(CertificateDecision).filter(CertificateDecision.id == decision_id).first()
    if not decision:
        raise HTTPException(status_code=404, detail="Certificate decision not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(decision, field, value)

    db.commit()
    db.refresh(decision)
    return decision


@router.delete("/{decision_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_certificate_decision(
    decision_id: UUID,
    db: Session = Depends(get_db),
    _ = Depends(require_roles("super_admin", "org_admin")),
):
    decision = db.query(CertificateDecision).filter(CertificateDecision.id == decision_id).first()
    if not decision:
        raise HTTPException(status_code=404, detail="Certificate decision not found")

    db.delete(decision)
    db.commit()
    return None

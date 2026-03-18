"""
Batch issuance service.

Expected CSV/Excel columns (case-insensitive):
  recipient_name, recipient_email, recipient_id, title,
  expires_at, [any custom_data columns prefixed with "custom_"]

Example CSV header:
  recipient_name,recipient_email,recipient_id,title,custom_score,custom_grade
"""
import csv
import io
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.certificate_batch import CertificateBatch
from app.models.certificate_decision import CertificateDecision
from app.models.organization import Organization
from app.models.template import Template
from app.schemas.certificate import CertIssueRequest
from app.services.certificate_service import issue_certificate

logger = logging.getLogger(__name__)

CORE_FIELDS = {"recipient_name", "recipient_email", "recipient_id", "title", "expires_at"}
VN_TZ = timezone(timedelta(hours=7))


def _parse_csv(content: bytes) -> list[dict]:
    text = content.decode("utf-8-sig")  # handle BOM
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for row in reader:
        cleaned = {k.strip().lower(): v.strip() for k, v in row.items() if k}
        rows.append(cleaned)
    return rows


def _parse_excel(content: bytes) -> list[dict]:
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    headers = [str(h).strip().lower() if h else "" for h in rows[0]]
    result = []
    for row in rows[1:]:
        if all(v is None for v in row):
            continue
        result.append({headers[i]: (str(v).strip() if v is not None else "") for i, v in enumerate(row)})
    return result


def _parse_datetime_flexible(raw_value: str) -> Optional[datetime]:
    value = (raw_value or "").strip()
    if not value:
        return None

    # Keep current behavior for ISO-like inputs first.
    try:
        dt = datetime.fromisoformat(value)
        return dt if dt.tzinfo else dt.replace(tzinfo=VN_TZ)
    except ValueError:
        pass

    # Common Vietnam date formats from Excel/manual input.
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d/%m/%Y %H:%M", "%d-%m-%Y %H:%M"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=VN_TZ)
        except ValueError:
            continue

    return None


def _row_to_issue_request(row: dict, template_id: uuid.UUID) -> CertIssueRequest:
    custom_data = {}
    for k, v in row.items():
        if k.startswith("custom_"):
            custom_data[k[7:]] = v  # strip "custom_" prefix

    expires_at = None
    if row.get("expires_at"):
        expires_at = _parse_datetime_flexible(row["expires_at"])

    return CertIssueRequest(
        template_id=template_id,
        recipient_name=row.get("recipient_name", ""),
        recipient_email=row.get("recipient_email") or None,
        recipient_id=row.get("recipient_id") or None,
        title=row.get("title", ""),
        custom_data=custom_data,
        expires_at=expires_at,
        registry_number=row.get("registry_number") or None,
    )


def _process_batch(
    db: Session,
    batch: CertificateBatch,
    file_content: bytes,
    filename: str,
    organization: Organization,
    issued_by_id: Optional[uuid.UUID] = None,
    actor_ip: Optional[str] = None,
) -> None:
    """
    Parse the uploaded file and issue certificates row by row.
    Updates batch counters in real time.
    """
    logger.info("Batch %s: start processing file '%s'", str(batch.id), filename)

    template = db.query(Template).filter(Template.id == batch.template_id).first()
    template_name = template.name if template else "Certificate"

    decision_number = None
    if batch.decision_id:
        decision = db.query(CertificateDecision).filter(CertificateDecision.id == batch.decision_id).first()
        if decision:
            decision_number = decision.decision_number

    default_title = template_name
    if decision_number:
        default_title = f"{template_name} - {decision_number}"

    # Parse file
    if filename.lower().endswith((".xlsx", ".xls")):
        rows = _parse_excel(file_content)
    else:
        rows = _parse_csv(file_content)

    logger.info("Batch %s: parsed %d rows", str(batch.id), len(rows))

    batch.total_count = len(rows)
    batch.status = "processing"
    batch.started_at = datetime.now(timezone.utc)
    db.flush()

    errors = []
    success = 0
    failed = 0

    for idx, row in enumerate(rows, start=1):
        try:
            issue_req = _row_to_issue_request(row, batch.template_id)
            if not issue_req.decision_id:
                issue_req.decision_id = batch.decision_id

            if not issue_req.title:
                issue_req.title = default_title

            # Auto-increment registry number if start number is provided and row has no registry number
            if not issue_req.registry_number and batch.registry_start_number is not None:
                current_num = batch.registry_start_number + idx - 1
                issue_req.registry_number = str(current_num)

            if not issue_req.recipient_name or not issue_req.title:
                raise ValueError("recipient_name and title are required")

            issue_certificate(
                db=db,
                payload=issue_req,
                organization=organization,
                issued_by_id=issued_by_id,
                actor_ip=actor_ip,
                batch_id=batch.id,
            )
            success += 1
        except Exception as exc:
            failed += 1
            errors.append({"row": idx, "error": str(exc), "data": row})
            logger.exception("Batch %s: row %d failed", str(batch.id), idx)

        # Update progress on every row
        batch.success_count = success
        batch.failed_count = failed
        batch.error_log = errors
        db.flush()

    batch.status = "completed" if failed == 0 else "completed_with_errors"
    batch.completed_at = datetime.now(timezone.utc)
    db.commit()
    logger.info(
        "Batch %s: finished with status=%s, total=%d, success=%d, failed=%d",
        str(batch.id),
        batch.status,
        batch.total_count,
        batch.success_count,
        batch.failed_count,
    )


def process_batch_task(
    batch_id: uuid.UUID,
    file_content: bytes,
    filename: str,
    organization_id: uuid.UUID,
    issued_by_id: Optional[uuid.UUID] = None,
    actor_ip: Optional[str] = None,
) -> None:
    """
    Background-task safe wrapper:
    create a fresh DB session, reload ORM entities, and capture fatal errors.
    """
    db: Session = SessionLocal()
    batch: Optional[CertificateBatch] = None
    try:
        batch = db.query(CertificateBatch).filter(CertificateBatch.id == batch_id).first()
        if not batch:
            logger.error("Batch %s: not found when background task started", str(batch_id))
            return

        organization = db.query(Organization).filter(Organization.id == organization_id).first()
        if not organization:
            batch.status = "failed"
            batch.completed_at = datetime.now(timezone.utc)
            batch.error_log = [{"row": 0, "error": "Organization not found for batch", "data": {}}]
            db.commit()
            logger.error("Batch %s: organization %s not found", str(batch_id), str(organization_id))
            return

        _process_batch(
            db=db,
            batch=batch,
            file_content=file_content,
            filename=filename,
            organization=organization,
            issued_by_id=issued_by_id,
            actor_ip=actor_ip,
        )
    except Exception as exc:
        logger.exception("Batch %s: fatal error in background task", str(batch_id))
        try:
            if batch:
                existing_errors = list(batch.error_log or [])
                existing_errors.append({"row": 0, "error": f"Fatal background error: {str(exc)}", "data": {}})
                batch.error_log = existing_errors
                batch.status = "failed"
                batch.completed_at = datetime.now(timezone.utc)
                db.commit()
        except Exception:
            db.rollback()
            logger.exception("Batch %s: unable to persist fatal error state", str(batch_id))
    finally:
        db.close()

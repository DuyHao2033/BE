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
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.certificate_batch import CertificateBatch
from app.models.organization import Organization
from app.schemas.certificate import CertIssueRequest
from app.services.certificate_service import issue_certificate


CORE_FIELDS = {"recipient_name", "recipient_email", "recipient_id", "title", "expires_at"}


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


def _row_to_issue_request(row: dict, template_id: uuid.UUID) -> CertIssueRequest:
    custom_data = {}
    for k, v in row.items():
        if k.startswith("custom_"):
            custom_data[k[7:]] = v  # strip "custom_" prefix

    expires_at = None
    if row.get("expires_at"):
        try:
            expires_at = datetime.fromisoformat(row["expires_at"])
        except ValueError:
            expires_at = None

    return CertIssueRequest(
        template_id=template_id,
        recipient_name=row.get("recipient_name", ""),
        recipient_email=row.get("recipient_email") or None,
        recipient_id=row.get("recipient_id") or None,
        title=row.get("title", ""),
        custom_data=custom_data,
        expires_at=expires_at,
    )


def process_batch(
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
    # Parse file
    if filename.lower().endswith((".xlsx", ".xls")):
        rows = _parse_excel(file_content)
    else:
        rows = _parse_csv(file_content)

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

        # Update progress on every row
        batch.success_count = success
        batch.failed_count = failed
        batch.error_log = errors
        db.flush()

    batch.status = "completed" if failed == 0 else "completed_with_errors"
    batch.completed_at = datetime.now(timezone.utc)
    db.commit()

import uuid
from datetime import datetime

from sqlalchemy import String, Boolean, TIMESTAMP, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, INET

from app.db.base import Base
from app.db.mixins import UUIDMixin


class VerifySession(Base, UUIDMixin):
    __tablename__ = "verify_sessions"

    certificate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("certificates.id")
    )

    cert_code: Mapped[str] = mapped_column(String(32), nullable=False)

    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=False)

    viewer_ip: Mapped[str | None] = mapped_column(INET)

    viewer_ua: Mapped[str | None] = mapped_column(String)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True)
    )

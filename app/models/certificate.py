import uuid
from datetime import datetime

from sqlalchemy import String, Text, TIMESTAMP, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.db.base import Base
from app.db.mixins import UUIDMixin, TimestampMixin


class Certificate(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "certificates"

    cert_code: Mapped[str] = mapped_column(
        String(32),
        unique=True,
        nullable=False
    )

    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("templates.id"),
        nullable=False
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False
    )

    issued_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id")
    )

    recipient_name: Mapped[str] = mapped_column(String(255), nullable=False)

    recipient_email: Mapped[str | None] = mapped_column(String(255))

    recipient_id: Mapped[str | None] = mapped_column(String(100))

    title: Mapped[str] = mapped_column(String(255), nullable=False)

    custom_data: Mapped[dict] = mapped_column(
        JSONB,
        server_default="{}"
    )

    status: Mapped[str] = mapped_column(
        String(30),
        server_default="active"
    )

    revoked_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True)
    )

    revoked_reason: Mapped[str | None] = mapped_column(Text)

    replaced_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("certificates.id")
    )

    expires_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True)
    )

    pdf_url: Mapped[str | None] = mapped_column(Text)

    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("certificate_batches.id")
    )

    issued_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True)
    )

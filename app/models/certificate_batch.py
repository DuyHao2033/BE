import uuid
from datetime import datetime

from sqlalchemy import String, Text, Integer, TIMESTAMP, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.db.base import Base
from app.db.mixins import UUIDMixin


class CertificateBatch(Base, UUIDMixin):
    __tablename__ = "certificate_batches"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False
    )

    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("templates.id"),
        nullable=False
    )

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id")
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    description: Mapped[str | None] = mapped_column(Text)

    source_file_url: Mapped[str | None] = mapped_column(Text)

    total_count: Mapped[int] = mapped_column(Integer, server_default="0")

    success_count: Mapped[int] = mapped_column(Integer, server_default="0")

    failed_count: Mapped[int] = mapped_column(Integer, server_default="0")

    status: Mapped[str] = mapped_column(
        String(30),
        server_default="pending"
    )

    error_log: Mapped[list] = mapped_column(
        JSONB,
        server_default="[]"
    )

    started_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True)
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True)
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True)
    )

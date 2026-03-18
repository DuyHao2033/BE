import uuid
from datetime import datetime

from sqlalchemy import String, Text, Boolean, TIMESTAMP, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.db.base import Base
from app.db.mixins import UUIDMixin, TimestampMixin


class Template(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "templates"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=True
    )

    certificate_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("certificate_types.id"),
        nullable=False
    )

    certificate_type: Mapped["CertificateType"] = relationship()

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    description: Mapped[str | None] = mapped_column(Text)

    category: Mapped[str | None] = mapped_column(String(100))

    page_size: Mapped[str] = mapped_column(String(20), server_default="A4")

    orientation: Mapped[str] = mapped_column(
        String(20),
        server_default="landscape"
    )

    background_url: Mapped[str | None] = mapped_column(Text)

    layout_json: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}"
    )

    custom_fields: Mapped[list] = mapped_column(
        JSONB,
        server_default="[]"
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        server_default="true"
    )

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id")
    )

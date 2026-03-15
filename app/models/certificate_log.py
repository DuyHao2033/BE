import uuid
from datetime import datetime

from sqlalchemy import String, Text, TIMESTAMP, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET

from app.db.base import Base
from app.db.mixins import UUIDMixin


class CertificateLog(Base, UUIDMixin):
    __tablename__ = "certificate_logs"

    certificate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("certificates.id"),
        nullable=False
    )

    event_type: Mapped[str] = mapped_column(String(50), nullable=False)

    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id")
    )

    actor_ip: Mapped[str | None] = mapped_column(INET)

    actor_ua: Mapped[str | None] = mapped_column(Text)

    extra_metadata: Mapped[dict] = mapped_column(
        JSONB,
        server_default="{}"
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True)
    )

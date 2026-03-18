import uuid
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base
from app.db.mixins import UUIDMixin, TimestampMixin


class CertificateType(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "certificate_types"

    code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    description: Mapped[str | None] = mapped_column(Text)

    # schema các field template được phép dùng
    field_schema: Mapped[dict] = mapped_column(
        JSONB,
        server_default="{}"
    )

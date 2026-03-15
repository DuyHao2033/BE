import uuid
from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import UUIDMixin, TimestampMixin


class Organization(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    slug: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False
    )

    logo_url: Mapped[str | None] = mapped_column(Text)

    website: Mapped[str | None] = mapped_column(Text)

    settings: Mapped[dict] = mapped_column(
        JSONB,
        server_default="{}"
    )

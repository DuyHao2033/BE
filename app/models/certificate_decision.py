import uuid
from datetime import date
from sqlalchemy import String, Text, Date
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import UUIDMixin, TimestampMixin


class CertificateDecision(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "certificate_decisions"

    decision_number: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    decision_date: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )

    title: Mapped[str | None] = mapped_column(Text)

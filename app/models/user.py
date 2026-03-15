import uuid

from sqlalchemy import Column, String, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.db.mixins import UUIDMixin, TimestampMixin


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=True
    )

    email = Column(String(255), unique=True, nullable=False)

    full_name = Column(String(255), nullable=False)

    role = Column(
        String(50),
        nullable=False
    )  # 'super_admin' | 'org_admin' | 'issuer'

    password_hash = Column(String, nullable=False)

    is_active = Column(Boolean, default=True)

    # relationships
    organization = relationship("Organization", backref="users")

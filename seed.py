#!/usr/bin/env python
"""
Seed script — creates an initial super_admin user and a sample organization.

Usage:
    source .venv/bin/activate
    python seed.py
"""
import sys
import os

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(__file__))

from app.db.session import SessionLocal
from app.models.user import User
from app.models.organization import Organization
from app.core.security import hash_password

ORG_NAME = "Trường Đại học Quốc tế SIU"
ORG_SLUG = "siu"
ADMIN_EMAIL = "admin@siu.edu.vn"
ADMIN_PASSWORD = "Admin@123"


def seed():
    db = SessionLocal()
    try:
        # Organization
        org = db.query(Organization).filter(Organization.slug == ORG_SLUG).first()
        if not org:
            org = Organization(
                name=ORG_NAME,
                slug=ORG_SLUG,
                website="https://siu.edu.vn",
                settings={},
            )
            db.add(org)
            db.flush()
            print(f"✅ Created organization: {ORG_NAME}")
        else:
            print(f"ℹ️  Organization already exists: {ORG_NAME}")

        # Super admin user
        user = db.query(User).filter(User.email == ADMIN_EMAIL).first()
        if not user:
            user = User(
                email=ADMIN_EMAIL,
                full_name="Super Admin",
                role="super_admin",
                password_hash=hash_password(ADMIN_PASSWORD),
                organization_id=org.id,
                is_active=True,
            )
            db.add(user)
            db.flush()
            print(f"✅ Created super_admin: {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
        else:
            print(f"ℹ️  User already exists: {ADMIN_EMAIL}")

        db.commit()
        print("\n🎉 Seed completed!")
        print(f"   Login: {ADMIN_EMAIL}")
        print(f"   Password: {ADMIN_PASSWORD}")

    except Exception as e:
        db.rollback()
        print(f"❌ Seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()

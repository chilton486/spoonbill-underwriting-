import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.services.auth import AuthService
from app.models.user import UserRole
from app.config import get_settings


def seed_admin():
    settings = get_settings()
    db = SessionLocal()
    try:
        existing = AuthService.get_user_by_email(db, settings.admin_email)
        if existing:
            print(f"Admin user already exists: {settings.admin_email}")
            return
        
        user = AuthService.create_user(
            db,
            email=settings.admin_email,
            password=settings.admin_password,
            role=UserRole.ADMIN,
        )
        print(f"Created admin user: {user.email} (role: {user.role})")
    finally:
        db.close()


if __name__ == "__main__":
    seed_admin()

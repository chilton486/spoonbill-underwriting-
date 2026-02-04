import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.services.auth import AuthService
from app.models.user import UserRole
from app.models.practice import Practice
from app.config import get_settings


def seed_admin():
    settings = get_settings()
    
    if not settings.admin_password:
        print("ERROR: ADMIN_PASSWORD environment variable is required.")
        print("Set it in your .env file or export it before running this command.")
        sys.exit(1)
    
    db = SessionLocal()
    try:
        existing = AuthService.get_user_by_email(db, settings.admin_email)
        if existing:
            print(f"Admin user already exists: {settings.admin_email}")
            print("No changes made. This is expected if you've already run this command.")
            return
        
        user = AuthService.create_user(
            db,
            email=settings.admin_email,
            password=settings.admin_password,
            role=UserRole.SPOONBILL_ADMIN,
        )
        print(f"Created admin user: {user.email} (role: {user.role})")
    finally:
        db.close()


def seed_demo_practice():
    db = SessionLocal()
    try:
        existing = db.query(Practice).filter(Practice.id == 1).first()
        if existing:
            print(f"Demo Practice already exists: {existing.name}")
            return existing
        
        practice = Practice(name="Demo Practice")
        db.add(practice)
        db.commit()
        db.refresh(practice)
        print(f"Created Demo Practice: {practice.name} (id: {practice.id})")
        return practice
    finally:
        db.close()


if __name__ == "__main__":
    seed_admin()

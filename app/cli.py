import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.services.auth import AuthService
from app.models.user import UserRole
from app.config import get_settings


def seed_admin():
    """Seed the initial admin user.
    
    This command is idempotent - if the admin user already exists, it will
    print a message and exit successfully without making changes.
    
    Requires ADMIN_PASSWORD to be set in environment or .env file.
    """
    settings = get_settings()
    
    if not settings.admin_password:
        print("ERROR: ADMIN_PASSWORD environment variable is required.")
        print("Set it in your .env file or export it before running this command.")
        print("Example: export ADMIN_PASSWORD='your-secure-password'")
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
            role=UserRole.ADMIN,
        )
        print(f"Created admin user: {user.email} (role: {user.role})")
    finally:
        db.close()


if __name__ == "__main__":
    seed_admin()

"""Practice Manager Invite model for secure password setup flow."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from ..database import Base


class PracticeManagerInvite(Base):
    """
    One-time invite tokens for practice managers to set their password.
    
    Created when an application is approved. The invite link is shared with
    the practice manager, who uses it to set their password and activate
    their account.
    
    Tokens are single-use and expire after 7 days.
    """
    __tablename__ = "practice_manager_invites"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token = Column(String(64), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="invites")
    
    @property
    def is_valid(self) -> bool:
        """Check if the invite is still valid (not used and not expired)."""
        if self.used_at is not None:
            return False
        if datetime.utcnow() > self.expires_at:
            return False
        return True

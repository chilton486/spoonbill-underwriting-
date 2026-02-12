"""Internal Practices API endpoints for Spoonbill Ops.

Provides practice management, invite link retrieval, and reissue functionality.
All endpoints require SPOONBILL_ADMIN or SPOONBILL_OPS role.
"""
import secrets
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from ..database import get_db
from ..config import get_settings
from ..models.practice import Practice
from ..models.user import User, UserRole
from ..models.claim import Claim
from ..models.invite import PracticeManagerInvite
from ..services.audit import AuditService
from .auth import require_spoonbill_role

router = APIRouter(prefix="/api/practices", tags=["internal-practices"])

# Invite token expiration (7 days)
INVITE_TOKEN_EXPIRY_DAYS = 7


# =============================================================================
# Response Schemas
# =============================================================================

class PracticeManagerResponse(BaseModel):
    """Practice manager user info."""
    id: int
    email: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class InviteResponse(BaseModel):
    """Invite info for display."""
    id: int
    user_id: int
    user_email: str
    token: str
    status: str  # ACTIVE, USED, EXPIRED
    created_at: datetime
    expires_at: datetime
    used_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PracticeListResponse(BaseModel):
    """Practice list item."""
    id: int
    name: str
    status: str
    created_at: datetime
    claim_count: int
    primary_manager_email: Optional[str] = None
    has_active_invite: bool

    class Config:
        from_attributes = True


class PracticeDetailResponse(BaseModel):
    """Full practice detail."""
    id: int
    name: str
    status: str
    created_at: datetime
    claim_count: int
    managers: List[PracticeManagerResponse]
    invites: List[InviteResponse]

    class Config:
        from_attributes = True


class ReissueInviteResponse(BaseModel):
    """Response after reissuing an invite."""
    invite_id: int
    user_id: int
    user_email: str
    token: str
    invite_url: str
    expires_at: datetime
    message: str


# =============================================================================
# Helper Functions
# =============================================================================

def get_invite_status(invite: PracticeManagerInvite) -> str:
    """Compute the status of an invite."""
    if invite.used_at is not None:
        return "USED"
    if datetime.utcnow() > invite.expires_at:
        return "EXPIRED"
    return "ACTIVE"


def get_practice_or_404(db: Session, practice_id: int) -> Practice:
    """Get practice by ID or raise 404."""
    practice = db.query(Practice).filter(Practice.id == practice_id).first()
    if not practice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Practice not found",
        )
    return practice


# =============================================================================
# Endpoints
# =============================================================================

@router.get("", response_model=List[PracticeListResponse])
def list_practices(
    q: Optional[str] = Query(None, description="Search by practice name, ID, or manager email"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_role),
):
    """
    List all practices with summary info.
    
    Requires SPOONBILL_ADMIN or SPOONBILL_OPS role.
    """
    query = db.query(Practice)
    
    # Apply search filter
    if q:
        search_term = f"%{q}%"
        # Get user IDs that match the email search
        matching_user_ids = db.query(User.practice_id).filter(
            User.email.ilike(search_term),
            User.role == UserRole.PRACTICE_MANAGER.value
        ).subquery()
        
        # Search by practice name, ID, or manager email
        query = query.filter(
            or_(
                Practice.name.ilike(search_term),
                Practice.id == int(q) if q.isdigit() else False,
                Practice.id.in_(matching_user_ids),
            )
        )
    
    practices = query.order_by(Practice.created_at.desc()).all()
    
    # Build response with additional computed fields
    result = []
    for practice in practices:
        # Get claim count
        claim_count = db.query(func.count(Claim.id)).filter(
            Claim.practice_id == practice.id
        ).scalar() or 0
        
        # Get primary manager (first active practice manager)
        primary_manager = db.query(User).filter(
            User.practice_id == practice.id,
            User.role == UserRole.PRACTICE_MANAGER.value,
            User.is_active.is_(True)
        ).first()
        
        # Check for active invite
        has_active_invite = False
        if primary_manager:
            active_invite = db.query(PracticeManagerInvite).filter(
                PracticeManagerInvite.user_id == primary_manager.id,
                PracticeManagerInvite.used_at.is_(None),
                PracticeManagerInvite.expires_at > datetime.utcnow()
            ).first()
            has_active_invite = active_invite is not None
        
        result.append(PracticeListResponse(
            id=practice.id,
            name=practice.name,
            status=practice.status,
            created_at=practice.created_at,
            claim_count=claim_count,
            primary_manager_email=primary_manager.email if primary_manager else None,
            has_active_invite=has_active_invite,
        ))
    
    return result


@router.get("/{practice_id}", response_model=PracticeDetailResponse)
def get_practice(
    practice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_role),
):
    """
    Get full practice detail including managers and invite history.
    
    Requires SPOONBILL_ADMIN or SPOONBILL_OPS role.
    """
    practice = get_practice_or_404(db, practice_id)
    
    # Get claim count
    claim_count = db.query(func.count(Claim.id)).filter(
        Claim.practice_id == practice.id
    ).scalar() or 0
    
    # Get all practice managers
    managers = db.query(User).filter(
        User.practice_id == practice.id,
        User.role == UserRole.PRACTICE_MANAGER.value
    ).order_by(User.created_at.asc()).all()
    
    # Get all invites for this practice's managers
    manager_ids = [m.id for m in managers]
    invites_raw = db.query(PracticeManagerInvite).filter(
        PracticeManagerInvite.user_id.in_(manager_ids)
    ).order_by(PracticeManagerInvite.created_at.desc()).all()
    
    # Build invite responses with computed status
    invites = []
    for invite in invites_raw:
        user = next((m for m in managers if m.id == invite.user_id), None)
        invites.append(InviteResponse(
            id=invite.id,
            user_id=invite.user_id,
            user_email=user.email if user else "unknown",
            token=invite.token,
            status=get_invite_status(invite),
            created_at=invite.created_at,
            expires_at=invite.expires_at,
            used_at=invite.used_at,
        ))
    
    return PracticeDetailResponse(
        id=practice.id,
        name=practice.name,
        status=practice.status,
        created_at=practice.created_at,
        claim_count=claim_count,
        managers=[PracticeManagerResponse(
            id=m.id,
            email=m.email,
            is_active=m.is_active,
            created_at=m.created_at,
        ) for m in managers],
        invites=invites,
    )


@router.get("/{practice_id}/invites", response_model=List[InviteResponse])
def list_practice_invites(
    practice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_role),
):
    """
    List all invites for a practice (latest first).
    
    Requires SPOONBILL_ADMIN or SPOONBILL_OPS role.
    """
    practice = get_practice_or_404(db, practice_id)
    
    # Get all practice managers
    managers = db.query(User).filter(
        User.practice_id == practice.id,
        User.role == UserRole.PRACTICE_MANAGER.value
    ).all()
    
    manager_ids = [m.id for m in managers]
    if not manager_ids:
        return []
    
    invites_raw = db.query(PracticeManagerInvite).filter(
        PracticeManagerInvite.user_id.in_(manager_ids)
    ).order_by(PracticeManagerInvite.created_at.desc()).all()
    
    invites = []
    for invite in invites_raw:
        user = next((m for m in managers if m.id == invite.user_id), None)
        invites.append(InviteResponse(
            id=invite.id,
            user_id=invite.user_id,
            user_email=user.email if user else "unknown",
            token=invite.token,
            status=get_invite_status(invite),
            created_at=invite.created_at,
            expires_at=invite.expires_at,
            used_at=invite.used_at,
        ))
    
    return invites


@router.post("/{practice_id}/invites/reissue", response_model=ReissueInviteResponse)
def reissue_invite(
    practice_id: int,
    user_id: Optional[int] = Query(None, description="Specific user ID to reissue invite for (defaults to primary manager)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_role),
):
    """
    Reissue an invite for a practice manager.
    
    - Expires any existing active invites for the user
    - Creates a new invite token (7 day expiry)
    - Logs audit event
    
    Requires SPOONBILL_ADMIN or SPOONBILL_OPS role.
    """
    practice = get_practice_or_404(db, practice_id)
    
    # Get the target user
    if user_id:
        target_user = db.query(User).filter(
            User.id == user_id,
            User.practice_id == practice.id,
            User.role == UserRole.PRACTICE_MANAGER.value
        ).first()
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Practice manager not found for this practice",
            )
    else:
        # Default to primary manager (first created)
        target_user = db.query(User).filter(
            User.practice_id == practice.id,
            User.role == UserRole.PRACTICE_MANAGER.value
        ).order_by(User.created_at.asc()).first()
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No practice manager found for this practice",
            )
    
    # Expire any existing active invites for this user
    existing_invites = db.query(PracticeManagerInvite).filter(
        PracticeManagerInvite.user_id == target_user.id,
        PracticeManagerInvite.used_at.is_(None),
        PracticeManagerInvite.expires_at > datetime.utcnow()
    ).all()
    
    expired_count = 0
    for invite in existing_invites:
        invite.expires_at = datetime.utcnow()  # Expire immediately
        expired_count += 1
    
    # Create new invite
    new_token = secrets.token_urlsafe(32)
    new_invite = PracticeManagerInvite(
        user_id=target_user.id,
        token=new_token,
        expires_at=datetime.utcnow() + timedelta(days=INVITE_TOKEN_EXPIRY_DAYS),
    )
    db.add(new_invite)
    db.flush()
    
    # Log audit event
    AuditService.log_event(
        db,
        claim_id=None,
        action="PRACTICE_INVITE_REISSUED",
        actor_user_id=current_user.id,
        metadata={
            "practice_id": practice.id,
            "practice_name": practice.name,
            "user_id": target_user.id,
            "user_email": target_user.email,
            "new_invite_id": new_invite.id,
            "expired_invite_count": expired_count,
            "expires_at": new_invite.expires_at.isoformat(),
        },
    )
    
    db.commit()
    
    # Build full invite URL using configured base URL
    settings = get_settings()
    invite_url = f"{settings.practice_portal_base_url}/set-password/{new_token}"
    
    return ReissueInviteResponse(
        invite_id=new_invite.id,
        user_id=target_user.id,
        user_email=target_user.email,
        token=new_token,
        invite_url=invite_url,
        expires_at=new_invite.expires_at,
        message=f"New invite created for {target_user.email}. {expired_count} previous invite(s) expired.",
    )

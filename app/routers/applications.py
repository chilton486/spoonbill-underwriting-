"""Practice Application API endpoints.

Public endpoints for intake form submission (no auth required).
Internal endpoints for Ops review (requires SPOONBILL_ADMIN or SPOONBILL_OPS role).
"""
import logging
import secrets
import string
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.auth import AuthService
from ..services.rate_limiter import application_rate_limiter
from ..models.practice_application import PracticeApplication, ApplicationStatus
from ..models.practice import Practice, PracticeStatus
from ..models.user import User, UserRole
from ..models.invite import PracticeManagerInvite
from ..schemas.practice_application import (
    PracticeApplicationCreate,
    PracticeApplicationResponse,
    PracticeApplicationListResponse,
    ApplicationReviewRequest,
    ApplicationApprovalResult,
    ApplicationSubmissionResponse,
)
from ..services.audit import AuditService
from .auth import require_spoonbill_role

logger = logging.getLogger(__name__)

router = APIRouter(tags=["applications"])

# Invite token expiration (7 days)
INVITE_TOKEN_EXPIRY_DAYS = 7


def get_client_ip(request: Request) -> str:
    """Extract client IP from request, handling proxies."""
    # Check for forwarded header (behind proxy/load balancer)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Take the first IP in the chain (original client)
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def generate_temporary_password(length: int = 16) -> str:
    """Generate a secure temporary password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


# =============================================================================
# PUBLIC ENDPOINTS (No authentication required)
# =============================================================================

@router.post(
    "/apply",
    response_model=ApplicationSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_application(
    application_data: PracticeApplicationCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Submit a practice application for Spoonbill.
    
    This is a PUBLIC endpoint - no authentication required.
    Creates a new practice application with status SUBMITTED.
    No login credentials are created until approval.
    
    Rate limited to 5 requests per hour per IP.
    """
    client_ip = get_client_ip(request)
    
    # Check rate limit
    is_allowed, remaining = application_rate_limiter.is_allowed(client_ip)
    if not is_allowed:
        logger.warning(
            "Rate limit exceeded for application submission",
            extra={
                "ip": client_ip,
                "email": application_data.contact_email,
                "rejection_reason": "RATE_LIMIT_EXCEEDED",
            }
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many application submissions. Please try again later.",
        )
    
    # Check honeypot field (bots fill all fields)
    if application_data.company_url:
        logger.warning(
            "Honeypot triggered for application submission",
            extra={
                "ip": client_ip,
                "rejection_reason": "HONEYPOT_TRIGGERED",
            }
        )
        # Return success to not reveal the honeypot to bots
        # but don't actually create the application
        return ApplicationSubmissionResponse(
            id=0,
            status="SUBMITTED",
            message="Your application has been submitted successfully. Our team will review it and contact you within 2-3 business days.",
        )
    
    # Record the request for rate limiting
    application_rate_limiter.record_request(client_ip)
    
    # Check for duplicate email (prevent spam/duplicate applications)
    existing = db.query(PracticeApplication).filter(
        PracticeApplication.contact_email == application_data.contact_email,
        PracticeApplication.status.in_([
            ApplicationStatus.SUBMITTED.value,
            ApplicationStatus.NEEDS_INFO.value,
        ])
    ).first()
    
    if existing:
        logger.info(
            "Duplicate application attempt",
            extra={
                "ip": client_ip,
                "email": application_data.contact_email,
                "rejection_reason": "DUPLICATE_EMAIL",
            }
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An application with this email is already pending review. Please contact support if you need to update your application.",
        )
    
    application = PracticeApplication(
        legal_name=application_data.legal_name,
        address=application_data.address,
        phone=application_data.phone,
        website=application_data.website,
        tax_id=application_data.tax_id,
        practice_type=application_data.practice_type.value,
        years_in_operation=application_data.years_in_operation,
        provider_count=application_data.provider_count,
        operatory_count=application_data.operatory_count,
        avg_monthly_collections_range=application_data.avg_monthly_collections_range,
        insurance_vs_self_pay_mix=application_data.insurance_vs_self_pay_mix,
        top_payers=application_data.top_payers,
        avg_ar_days=application_data.avg_ar_days,
        billing_model=application_data.billing_model.value,
        follow_up_frequency=application_data.follow_up_frequency,
        practice_management_software=application_data.practice_management_software,
        claims_per_month=application_data.claims_per_month,
        electronic_claims=application_data.electronic_claims,
        stated_goal=application_data.stated_goal,
        urgency_level=application_data.urgency_level.value,
        contact_name=application_data.contact_name,
        contact_email=application_data.contact_email,
        contact_phone=application_data.contact_phone,
        status=ApplicationStatus.SUBMITTED.value,
    )
    
    db.add(application)
    db.commit()
    db.refresh(application)
    
    return ApplicationSubmissionResponse(
        id=application.id,
        status=application.status,
        message="Your application has been submitted successfully. Our team will review it and contact you within 2-3 business days.",
    )


@router.get(
    "/apply/status/{application_id}",
    response_model=PracticeApplicationListResponse,
)
def check_application_status(
    application_id: int,
    email: str = Query(..., description="Contact email used in application"),
    db: Session = Depends(get_db),
):
    """
    Check the status of a submitted application.
    
    This is a PUBLIC endpoint - requires application ID and matching email.
    """
    application = db.query(PracticeApplication).filter(
        PracticeApplication.id == application_id,
        PracticeApplication.contact_email == email,
    ).first()
    
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found. Please verify your application ID and email.",
        )
    
    return application


# =============================================================================
# INTERNAL ENDPOINTS (Requires Spoonbill role)
# =============================================================================

@router.get(
    "/internal/applications",
    response_model=List[PracticeApplicationListResponse],
)
def list_applications(
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_role),
):
    """
    List all practice applications for Ops review.
    
    Requires SPOONBILL_ADMIN or SPOONBILL_OPS role.
    """
    query = db.query(PracticeApplication)
    
    if status_filter:
        query = query.filter(PracticeApplication.status == status_filter)
    
    # Order by urgency (CRITICAL first) then by created_at (oldest first for FIFO)
    urgency_order = {
        "CRITICAL": 0,
        "HIGH": 1,
        "MEDIUM": 2,
        "LOW": 3,
    }
    
    applications = query.order_by(
        PracticeApplication.created_at.asc()
    ).all()
    
    # Sort by urgency in Python (SQLite doesn't support CASE easily)
    applications.sort(key=lambda a: (urgency_order.get(a.urgency_level, 2), a.created_at))
    
    return applications


@router.get(
    "/internal/applications/{application_id}",
    response_model=PracticeApplicationResponse,
)
def get_application(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_role),
):
    """
    Get full details of a practice application.
    
    Requires SPOONBILL_ADMIN or SPOONBILL_OPS role.
    """
    application = db.query(PracticeApplication).filter(
        PracticeApplication.id == application_id
    ).first()
    
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )
    
    return application


@router.post(
    "/internal/applications/{application_id}/review",
)
def review_application(
    application_id: int,
    review: ApplicationReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_role),
):
    """
    Review a practice application: APPROVE, DECLINE, or request NEEDS_INFO.
    
    Requires SPOONBILL_ADMIN or SPOONBILL_OPS role.
    
    On APPROVE:
    - Creates a new Practice
    - Creates a PRACTICE_MANAGER user with temporary password
    - Links application to created practice
    - Returns credentials for the new manager
    
    On DECLINE:
    - Marks application as DECLINED
    - No practice or user created
    - Application remains for audit history
    
    On NEEDS_INFO:
    - Marks application as NEEDS_INFO
    - Ops should contact applicant for additional information
    """
    application = db.query(PracticeApplication).filter(
        PracticeApplication.id == application_id
    ).first()
    
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )
    
    # Validate current status allows review
    if application.status not in [ApplicationStatus.SUBMITTED.value, ApplicationStatus.NEEDS_INFO.value]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot review application in status {application.status}. Only SUBMITTED or NEEDS_INFO applications can be reviewed.",
        )
    
    old_status = application.status
    
    if review.action == "APPROVE":
        return _approve_application(db, application, current_user, review.review_notes)
    
    elif review.action == "DECLINE":
        application.status = ApplicationStatus.DECLINED.value
        application.review_notes = review.review_notes
        application.reviewed_by_user_id = current_user.id
        application.reviewed_at = datetime.utcnow()
        
        # Log audit event
        AuditService.log_event(
            db,
            claim_id=None,
            action="APPLICATION_DECLINED",
            actor_user_id=current_user.id,
            metadata={
                "application_id": application.id,
                "legal_name": application.legal_name,
                "old_status": old_status,
                "review_notes": review.review_notes,
            },
        )
        
        db.commit()
        
        return {
            "application_id": application.id,
            "status": application.status,
            "message": "Application has been declined.",
        }
    
    elif review.action == "NEEDS_INFO":
        application.status = ApplicationStatus.NEEDS_INFO.value
        application.review_notes = review.review_notes
        application.reviewed_by_user_id = current_user.id
        application.reviewed_at = datetime.utcnow()
        
        # Log audit event
        AuditService.log_event(
            db,
            claim_id=None,
            action="APPLICATION_NEEDS_INFO",
            actor_user_id=current_user.id,
            metadata={
                "application_id": application.id,
                "legal_name": application.legal_name,
                "old_status": old_status,
                "review_notes": review.review_notes,
            },
        )
        
        db.commit()
        
        return {
            "application_id": application.id,
            "status": application.status,
            "message": "Application marked as needing additional information. Please contact the applicant.",
        }
    
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid action: {review.action}. Must be APPROVE, DECLINE, or NEEDS_INFO.",
        )


def _approve_application(
    db: Session,
    application: PracticeApplication,
    current_user: User,
    review_notes: Optional[str],
) -> ApplicationApprovalResult:
    """
    Internal function to handle application approval.
    
    Creates practice, manager user with random password (never shown),
    and generates a one-time invite token for password setup.
    """
    # Check if email is already in use
    existing_user = db.query(User).filter(User.email == application.contact_email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A user with email {application.contact_email} already exists. Please use a different email or contact support.",
        )
    
    old_status = application.status
    
    # Create the practice
    practice = Practice(
        name=application.legal_name,
        status=PracticeStatus.ACTIVE.value,
    )
    db.add(practice)
    db.flush()  # Get practice.id
    
    # Generate a random strong password (never shown to anyone)
    # User will set their own password via invite link
    random_password = secrets.token_urlsafe(32)
    
    # Create the practice manager user (inactive until password is set)
    manager = User(
        email=application.contact_email,
        password_hash=AuthService.get_password_hash(random_password),
        role=UserRole.PRACTICE_MANAGER.value,
        practice_id=practice.id,
        is_active=False,  # Inactive until password is set via invite
    )
    db.add(manager)
    db.flush()  # Get manager.id
    
    # Generate invite token (single-use, expires in 7 days)
    invite_token = secrets.token_urlsafe(32)
    invite = PracticeManagerInvite(
        user_id=manager.id,
        token=invite_token,
        expires_at=datetime.utcnow() + timedelta(days=INVITE_TOKEN_EXPIRY_DAYS),
    )
    db.add(invite)
    
    # Update application status
    application.status = ApplicationStatus.APPROVED.value
    application.review_notes = review_notes
    application.reviewed_by_user_id = current_user.id
    application.reviewed_at = datetime.utcnow()
    application.created_practice_id = practice.id
    
    # Log audit event for application approval
    AuditService.log_event(
        db,
        claim_id=None,
        action="APPLICATION_APPROVED",
        actor_user_id=current_user.id,
        metadata={
            "application_id": application.id,
            "legal_name": application.legal_name,
            "old_status": old_status,
            "practice_id": practice.id,
            "manager_user_id": manager.id,
            "manager_email": manager.email,
            "review_notes": review_notes,
        },
    )
    
    # Log audit event for practice creation
    AuditService.log_event(
        db,
        claim_id=None,
        action="PRACTICE_CREATED",
        actor_user_id=current_user.id,
        metadata={
            "practice_id": practice.id,
            "practice_name": practice.name,
            "from_application_id": application.id,
        },
    )
    
    # Log audit event for user creation
    AuditService.log_event(
        db,
        claim_id=None,
        action="USER_CREATED",
        actor_user_id=current_user.id,
        metadata={
            "user_id": manager.id,
            "email": manager.email,
            "role": manager.role,
            "practice_id": practice.id,
            "from_application_id": application.id,
        },
    )
    
    # Log audit event for invite creation
    AuditService.log_event(
        db,
        claim_id=None,
        action="INVITE_CREATED",
        actor_user_id=current_user.id,
        metadata={
            "invite_id": invite.id if invite.id else "pending",
            "user_id": manager.id,
            "expires_at": invite.expires_at.isoformat(),
        },
    )
    
    db.commit()
    
    return ApplicationApprovalResult(
        application_id=application.id,
        practice_id=practice.id,
        manager_user_id=manager.id,
        manager_email=manager.email,
        invite_token=invite_token,
        message=f"Application approved. Practice '{practice.name}' created. Share the invite link with the practice manager to set their password.",
    )


@router.get(
    "/internal/applications/stats",
)
def get_application_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_role),
):
    """
    Get statistics on practice applications.
    
    Requires SPOONBILL_ADMIN or SPOONBILL_OPS role.
    """
    total = db.query(PracticeApplication).count()
    submitted = db.query(PracticeApplication).filter(
        PracticeApplication.status == ApplicationStatus.SUBMITTED.value
    ).count()
    needs_info = db.query(PracticeApplication).filter(
        PracticeApplication.status == ApplicationStatus.NEEDS_INFO.value
    ).count()
    approved = db.query(PracticeApplication).filter(
        PracticeApplication.status == ApplicationStatus.APPROVED.value
    ).count()
    declined = db.query(PracticeApplication).filter(
        PracticeApplication.status == ApplicationStatus.DECLINED.value
    ).count()
    
    return {
        "total": total,
        "pending_review": submitted + needs_info,
        "submitted": submitted,
        "needs_info": needs_info,
        "approved": approved,
        "declined": declined,
    }


# =============================================================================
# INVITE / SET PASSWORD ENDPOINTS (Public)
# =============================================================================

class SetPasswordRequest(BaseModel):
    """Request schema for setting password via invite token."""
    token: str = Field(..., min_length=1)
    password: str = Field(..., min_length=8, max_length=128)


class SetPasswordResponse(BaseModel):
    """Response after setting password."""
    success: bool
    email: str
    message: str


@router.get("/invite/{token}")
def validate_invite_token(
    token: str,
    db: Session = Depends(get_db),
):
    """
    Validate an invite token and return basic info.
    
    This is a PUBLIC endpoint - no authentication required.
    Used by the set-password page to verify the token before showing the form.
    """
    invite = db.query(PracticeManagerInvite).filter(
        PracticeManagerInvite.token == token
    ).first()
    
    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired invite link.",
        )
    
    if invite.used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This invite link has already been used. Please contact support if you need assistance.",
        )
    
    if datetime.utcnow() > invite.expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This invite link has expired. Please contact support to request a new invite.",
        )
    
    user = db.query(User).filter(User.id == invite.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account not found.",
        )
    
    return {
        "valid": True,
        "email": user.email,
        "expires_at": invite.expires_at.isoformat(),
    }


@router.post("/set-password", response_model=SetPasswordResponse)
def set_password(
    request_data: SetPasswordRequest,
    db: Session = Depends(get_db),
):
    """
    Set password using an invite token.
    
    This is a PUBLIC endpoint - no authentication required.
    The token is single-use and expires after 7 days.
    """
    invite = db.query(PracticeManagerInvite).filter(
        PracticeManagerInvite.token == request_data.token
    ).first()
    
    if not invite:
        logger.warning(
            "Invalid invite token used",
            extra={"rejection_reason": "INVALID_TOKEN"}
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired invite link.",
        )
    
    if invite.used_at is not None:
        logger.warning(
            "Already-used invite token attempted",
            extra={"invite_id": invite.id, "rejection_reason": "TOKEN_ALREADY_USED"}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This invite link has already been used.",
        )
    
    if datetime.utcnow() > invite.expires_at:
        logger.warning(
            "Expired invite token attempted",
            extra={"invite_id": invite.id, "rejection_reason": "TOKEN_EXPIRED"}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This invite link has expired. Please contact support to request a new invite.",
        )
    
    user = db.query(User).filter(User.id == invite.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account not found.",
        )
    
    # Update user's password and activate account
    user.password_hash = AuthService.get_password_hash(request_data.password)
    user.is_active = True
    
    # Mark invite as used
    invite.used_at = datetime.utcnow()
    
    # Log audit event
    AuditService.log_event(
        db,
        claim_id=None,
        action="PASSWORD_SET_VIA_INVITE",
        actor_user_id=user.id,
        metadata={
            "user_id": user.id,
            "email": user.email,
            "invite_id": invite.id,
        },
    )
    
    db.commit()
    
    logger.info(
        "Password set successfully via invite",
        extra={"user_id": user.id, "email": user.email}
    )
    
    return SetPasswordResponse(
        success=True,
        email=user.email,
        message="Password set successfully. You can now log in to the Practice Portal.",
    )

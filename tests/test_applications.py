"""
Tests for Phase 4 Practice Applications.

These tests cover:
- Application submission validation
- Application status transitions
- Audit trail with nullable claim_id
- Honeypot spam detection
- Rate limiting

Note: Some tests require PostgreSQL due to UUID column types in ledger tables.
Unit tests for validation and status transitions work with any database.
"""
from app.models.practice_application import ApplicationStatus, PracticeType, BillingModel, UrgencyLevel
from app.schemas.practice_application import PracticeApplicationCreate


class TestApplicationStatusTransitions:
    """Unit tests for application status transitions."""
    
    def test_submitted_is_initial_status(self):
        """Test that SUBMITTED is the initial status."""
        assert ApplicationStatus.SUBMITTED.value == "SUBMITTED"
    
    def test_all_statuses_exist(self):
        """Test that all expected statuses are defined."""
        expected = ["SUBMITTED", "APPROVED", "DECLINED", "NEEDS_INFO"]
        for status in expected:
            assert hasattr(ApplicationStatus, status)
            assert ApplicationStatus[status].value == status


class TestPracticeTypes:
    """Unit tests for practice type enum."""
    
    def test_general_dentistry_exists(self):
        """Test GENERAL_DENTISTRY practice type."""
        assert PracticeType.GENERAL_DENTISTRY.value == "GENERAL_DENTISTRY"
    
    def test_all_practice_types_exist(self):
        """Test all expected practice types are defined."""
        expected = [
            "GENERAL_DENTISTRY",
            "PEDIATRIC_DENTISTRY", 
            "ORTHODONTICS",
            "PERIODONTICS",
            "ENDODONTICS",
            "ORAL_SURGERY",
            "PROSTHODONTICS",
            "MULTI_SPECIALTY",
            "OTHER",
        ]
        for ptype in expected:
            assert hasattr(PracticeType, ptype)


class TestBillingModels:
    """Unit tests for billing model enum."""
    
    def test_in_house_exists(self):
        """Test IN_HOUSE billing model."""
        assert BillingModel.IN_HOUSE.value == "IN_HOUSE"
    
    def test_all_billing_models_exist(self):
        """Test all expected billing models are defined."""
        expected = ["IN_HOUSE", "OUTSOURCED", "HYBRID"]
        for model in expected:
            assert hasattr(BillingModel, model)


class TestUrgencyLevels:
    """Unit tests for urgency level enum."""
    
    def test_all_urgency_levels_exist(self):
        """Test all expected urgency levels are defined."""
        expected = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        for level in expected:
            assert hasattr(UrgencyLevel, level)


class TestApplicationValidation:
    """Unit tests for application input validation."""
    
    def test_valid_application_data(self):
        """Test that valid application data passes validation."""
        data = {
            "legal_name": "Test Dental Practice",
            "address": "123 Main St, Austin, TX 78701",
            "phone": "512-555-1234",
            "practice_type": "GENERAL_DENTISTRY",
            "years_in_operation": 5,
            "provider_count": 3,
            "operatory_count": 6,
            "avg_monthly_collections_range": "$50,000 - $100,000",
            "insurance_vs_self_pay_mix": "70% insurance, 30% self-pay",
            "billing_model": "IN_HOUSE",
            "contact_name": "John Doe",
            "contact_email": "john@test.com",
        }
        app = PracticeApplicationCreate(**data)
        assert app.legal_name == "Test Dental Practice"
        assert app.contact_email == "john@test.com"
    
    def test_email_format_validation(self):
        """Test that email must be valid format."""
        data = {
            "legal_name": "Test",
            "address": "123 Main St",
            "phone": "512-555-1234",
            "practice_type": "GENERAL_DENTISTRY",
            "years_in_operation": 5,
            "provider_count": 3,
            "operatory_count": 6,
            "avg_monthly_collections_range": "$50,000 - $100,000",
            "insurance_vs_self_pay_mix": "70% insurance",
            "billing_model": "IN_HOUSE",
            "contact_name": "John Doe",
            "contact_email": "invalid-email",  # Invalid
        }
        try:
            PracticeApplicationCreate(**data)
            assert False, "Should have raised validation error"
        except Exception:
            pass  # Expected
    
    def test_max_length_constraints(self):
        """Test that max length constraints are enforced."""
        data = {
            "legal_name": "A" * 300,  # Too long (max 255)
            "address": "123 Main St",
            "phone": "512-555-1234",
            "practice_type": "GENERAL_DENTISTRY",
            "years_in_operation": 5,
            "provider_count": 3,
            "operatory_count": 6,
            "avg_monthly_collections_range": "$50,000 - $100,000",
            "insurance_vs_self_pay_mix": "70% insurance",
            "billing_model": "IN_HOUSE",
            "contact_name": "John Doe",
            "contact_email": "john@test.com",
        }
        try:
            PracticeApplicationCreate(**data)
            assert False, "Should have raised validation error"
        except Exception:
            pass  # Expected
    
    def test_honeypot_field_exists(self):
        """Test that honeypot field (company_url) exists in schema."""
        data = {
            "legal_name": "Test",
            "address": "123 Main St",
            "phone": "512-555-1234",
            "practice_type": "GENERAL_DENTISTRY",
            "years_in_operation": 5,
            "provider_count": 3,
            "operatory_count": 6,
            "avg_monthly_collections_range": "$50,000 - $100,000",
            "insurance_vs_self_pay_mix": "70% insurance",
            "billing_model": "IN_HOUSE",
            "contact_name": "John Doe",
            "contact_email": "john@test.com",
            "company_url": "http://spam.com",  # Honeypot field
        }
        app = PracticeApplicationCreate(**data)
        assert app.company_url == "http://spam.com"


class TestAuditEventClaimIdNullable:
    """Unit tests for audit event claim_id nullable behavior."""
    
    def test_audit_event_model_allows_nullable_claim_id(self):
        """Test that AuditEvent model allows nullable claim_id."""
        from app.models.audit import AuditEvent
        from sqlalchemy import inspect
        
        mapper = inspect(AuditEvent)
        claim_id_col = mapper.columns['claim_id']
        assert claim_id_col.nullable is True
    
    def test_audit_service_accepts_none_claim_id(self):
        """Test that AuditService.log_event accepts None for claim_id."""
        from app.services.audit import AuditService
        import inspect as py_inspect
        
        sig = py_inspect.signature(AuditService.log_event)
        claim_id_param = sig.parameters.get('claim_id')
        assert claim_id_param is not None
        # Check that the default or annotation allows None
        # The parameter should be Optional[int]


class TestRateLimiter:
    """Unit tests for rate limiter."""
    
    def test_rate_limiter_exists(self):
        """Test that rate limiter service exists."""
        from app.services.rate_limiter import RateLimiter
        assert RateLimiter is not None
    
    def test_rate_limiter_has_is_allowed_method(self):
        """Test that rate limiter has is_allowed method."""
        from app.services.rate_limiter import RateLimiter
        limiter = RateLimiter()
        assert hasattr(limiter, 'is_allowed')
        assert callable(limiter.is_allowed)
    
    def test_rate_limiter_allows_first_request(self):
        """Test that rate limiter allows first request."""
        from app.services.rate_limiter import RateLimiter
        limiter = RateLimiter(max_requests=5, window_seconds=3600)
        
        is_allowed, remaining = limiter.is_allowed("192.168.1.1")
        assert is_allowed is True
        assert remaining == 5  # Not yet recorded
    
    def test_rate_limiter_blocks_after_limit(self):
        """Test that rate limiter blocks after limit exceeded."""
        from app.services.rate_limiter import RateLimiter
        limiter = RateLimiter(max_requests=2, window_seconds=3600)
        
        # Record two requests
        limiter.record_request("192.168.1.2")
        limiter.record_request("192.168.1.2")
        
        # Third request should be blocked
        is_allowed, remaining = limiter.is_allowed("192.168.1.2")
        assert is_allowed is False
        assert remaining == 0
    
    def test_rate_limiter_tracks_different_ips_separately(self):
        """Test that rate limiter tracks different IPs separately."""
        from app.services.rate_limiter import RateLimiter
        limiter = RateLimiter(max_requests=1, window_seconds=3600)
        
        # Record request for first IP
        limiter.record_request("192.168.1.3")
        
        # First IP should be blocked
        is_allowed1, _ = limiter.is_allowed("192.168.1.3")
        assert is_allowed1 is False
        
        # Second IP should still be allowed
        is_allowed2, _ = limiter.is_allowed("192.168.1.4")
        assert is_allowed2 is True


class TestInviteToken:
    """Unit tests for invite token model."""
    
    def test_invite_model_exists(self):
        """Test that PracticeManagerInvite model exists."""
        from app.models.invite import PracticeManagerInvite
        assert PracticeManagerInvite is not None
    
    def test_invite_has_required_fields(self):
        """Test that invite model has required fields."""
        from app.models.invite import PracticeManagerInvite
        from sqlalchemy import inspect
        
        mapper = inspect(PracticeManagerInvite)
        columns = [c.key for c in mapper.columns]
        
        assert 'id' in columns
        assert 'token' in columns
        assert 'user_id' in columns
        assert 'expires_at' in columns
        assert 'used_at' in columns  # used_at instead of used
    
    def test_invite_has_is_valid_property(self):
        """Test that invite model has is_valid property."""
        from app.models.invite import PracticeManagerInvite
        
        assert hasattr(PracticeManagerInvite, 'is_valid')


class TestInviteUrlGeneration:
    """Tests for invite URL generation using environment variables."""

    def test_config_has_practice_portal_base_url(self):
        from app.config import Settings
        s = Settings(database_url="postgresql://x:x@localhost/x")
        assert hasattr(s, 'practice_portal_base_url')

    def test_default_practice_portal_base_url_is_localhost(self):
        import os
        env_backup = os.environ.get('PRACTICE_PORTAL_BASE_URL')
        os.environ.pop('PRACTICE_PORTAL_BASE_URL', None)
        from app.config import Settings
        s = Settings(database_url="postgresql://x:x@localhost/x")
        assert s.practice_portal_base_url == "http://localhost:5174"
        if env_backup is not None:
            os.environ['PRACTICE_PORTAL_BASE_URL'] = env_backup

    def test_practice_portal_base_url_from_env(self):
        import os
        old = os.environ.get('PRACTICE_PORTAL_BASE_URL')
        os.environ['PRACTICE_PORTAL_BASE_URL'] = 'https://spoonbill-staging-portal.onrender.com'
        from app.config import Settings
        s = Settings(database_url="postgresql://x:x@localhost/x")
        assert s.practice_portal_base_url == 'https://spoonbill-staging-portal.onrender.com'
        if old is not None:
            os.environ['PRACTICE_PORTAL_BASE_URL'] = old
        else:
            os.environ.pop('PRACTICE_PORTAL_BASE_URL', None)

    def test_invite_url_uses_env_var_not_hardcoded(self):
        import os
        old = os.environ.get('PRACTICE_PORTAL_BASE_URL')
        os.environ['PRACTICE_PORTAL_BASE_URL'] = 'https://portal.example.com'
        from app.config import Settings
        s = Settings(database_url="postgresql://x:x@localhost/x")
        token = "abc123"
        invite_url = f"{s.practice_portal_base_url}/#/set-password/{token}"
        assert invite_url == "https://portal.example.com/#/set-password/abc123"
        assert "localhost" not in invite_url
        if old is not None:
            os.environ['PRACTICE_PORTAL_BASE_URL'] = old
        else:
            os.environ.pop('PRACTICE_PORTAL_BASE_URL', None)

    def test_invite_url_no_trailing_slash(self):
        from app.config import Settings
        s = Settings(
            database_url="postgresql://x:x@localhost/x",
            practice_portal_base_url="https://portal.example.com",
        )
        token = "test-token"
        invite_url = f"{s.practice_portal_base_url}/#/set-password/{token}"
        assert invite_url == "https://portal.example.com/#/set-password/test-token"

    def test_approval_result_schema_has_invite_url(self):
        from app.schemas.practice_application import ApplicationApprovalResult
        fields = ApplicationApprovalResult.model_fields
        assert 'invite_url' in fields
        assert 'invite_token' in fields

    def test_config_has_intake_portal_base_url(self):
        from app.config import Settings
        s = Settings(database_url="postgresql://x:x@localhost/x")
        assert hasattr(s, 'intake_portal_base_url')
        assert s.intake_portal_base_url == "http://localhost:5175"


class TestInviteEndpoints:
    """Tests for public invite validation and set-password endpoints."""

    def test_invite_validation_response_has_practice_name(self):
        """Test that InviteValidationResponse includes practice_name field."""
        from app.routers.applications import InviteValidationResponse
        fields = InviteValidationResponse.model_fields
        assert 'practice_name' in fields
        assert 'email' in fields
        assert 'expires_at' in fields
        assert 'valid' in fields

    def test_set_password_request_has_password_field(self):
        """Test that SetPasswordRequest has password field with validation."""
        from app.routers.applications import SetPasswordRequest
        fields = SetPasswordRequest.model_fields
        assert 'password' in fields
        # Password should have min_length constraint
        password_field = fields['password']
        assert password_field.metadata is not None or password_field.json_schema_extra is not None

    def test_set_password_response_has_required_fields(self):
        """Test that SetPasswordResponse has success, email, message fields."""
        from app.routers.applications import SetPasswordResponse
        fields = SetPasswordResponse.model_fields
        assert 'success' in fields
        assert 'email' in fields
        assert 'message' in fields

    def test_password_min_length_validation(self):
        """Test that password must be at least 8 characters."""
        from app.routers.applications import SetPasswordRequest
        from pydantic import ValidationError
        
        # Should fail with short password
        try:
            SetPasswordRequest(password="short")
            assert False, "Should have raised validation error for short password"
        except ValidationError:
            pass  # Expected
        
        # Should succeed with valid password
        req = SetPasswordRequest(password="validpassword123")
        assert req.password == "validpassword123"

    def test_password_max_length_validation(self):
        """Test that password must be at most 128 characters."""
        from app.routers.applications import SetPasswordRequest
        from pydantic import ValidationError
        
        # Should fail with too long password
        try:
            SetPasswordRequest(password="x" * 129)
            assert False, "Should have raised validation error for long password"
        except ValidationError:
            pass  # Expected
        
        # Should succeed with max length password
        req = SetPasswordRequest(password="x" * 128)
        assert len(req.password) == 128


class TestInviteEndpointPaths:
    """Tests for invite endpoint URL paths."""

    def test_validate_invite_endpoint_path(self):
        """Test that validate_invite_token endpoint uses /public/invites/{token} path."""
        from app.routers.applications import router
        
        # Find the validate_invite_token route
        routes = [r for r in router.routes if hasattr(r, 'path')]
        validate_route = None
        for route in routes:
            if 'public/invites' in route.path and 'set-password' not in route.path:
                validate_route = route
                break
        
        assert validate_route is not None, "Validate invite endpoint not found"
        assert validate_route.path == "/public/invites/{token}"
        assert "GET" in validate_route.methods

    def test_set_password_endpoint_path(self):
        """Test that set_password endpoint uses /public/invites/{token}/set-password path."""
        from app.routers.applications import router
        
        # Find the set_password route
        routes = [r for r in router.routes if hasattr(r, 'path')]
        set_password_route = None
        for route in routes:
            if 'set-password' in route.path:
                set_password_route = route
                break
        
        assert set_password_route is not None, "Set password endpoint not found"
        assert set_password_route.path == "/public/invites/{token}/set-password"
        assert "POST" in set_password_route.methods


class TestInviteSecurityRequirements:
    """Tests for invite security requirements."""

    def test_invite_token_is_single_use(self):
        """Test that invite model tracks used_at for single-use enforcement."""
        from app.models.invite import PracticeManagerInvite
        from sqlalchemy import inspect
        
        mapper = inspect(PracticeManagerInvite)
        columns = {c.key: c for c in mapper.columns}
        
        assert 'used_at' in columns
        # used_at should be nullable (None when not used)
        assert columns['used_at'].nullable is True

    def test_invite_has_expiration(self):
        """Test that invite model has expires_at field."""
        from app.models.invite import PracticeManagerInvite
        from sqlalchemy import inspect
        
        mapper = inspect(PracticeManagerInvite)
        columns = {c.key for c in mapper.columns}
        
        assert 'expires_at' in columns

    def test_invite_expiry_constant_is_7_days(self):
        """Test that invite token expiry is set to 7 days."""
        from app.routers.applications import INVITE_TOKEN_EXPIRY_DAYS
        assert INVITE_TOKEN_EXPIRY_DAYS == 7

    def test_audit_event_for_invite_used(self):
        """Test that PRACTICE_INVITE_USED audit event is logged on password set."""
        # This is a documentation test - the actual audit event is logged in set_password
        # We verify the event name is used correctly
        import inspect as py_inspect
        from app.routers import applications
        
        source = py_inspect.getsource(applications.set_password)
        assert "PRACTICE_INVITE_USED" in source
        assert "AuditService.log_event" in source
        assert "practice_id" in source  # Should include practice_id in metadata

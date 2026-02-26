from pydantic import ValidationError
import pytest


class TestPracticeApplicationPatchSchema:

    def test_patch_accepts_partial_fields(self):
        from app.schemas.practice_application import PracticeApplicationPatch
        patch = PracticeApplicationPatch(legal_name="New Name")
        dumped = patch.model_dump(exclude_unset=True)
        assert dumped == {"legal_name": "New Name"}

    def test_patch_empty_is_valid(self):
        from app.schemas.practice_application import PracticeApplicationPatch
        patch = PracticeApplicationPatch()
        dumped = patch.model_dump(exclude_unset=True)
        assert dumped == {}

    def test_patch_email_must_be_valid(self):
        from app.schemas.practice_application import PracticeApplicationPatch
        with pytest.raises(ValidationError):
            PracticeApplicationPatch(contact_email="not-an-email")

    def test_patch_valid_email_accepted(self):
        from app.schemas.practice_application import PracticeApplicationPatch
        patch = PracticeApplicationPatch(contact_email="new@example.com")
        assert patch.contact_email == "new@example.com"

    def test_patch_legal_name_min_length(self):
        from app.schemas.practice_application import PracticeApplicationPatch
        with pytest.raises(ValidationError):
            PracticeApplicationPatch(legal_name="")

    def test_patch_legal_name_max_length(self):
        from app.schemas.practice_application import PracticeApplicationPatch
        with pytest.raises(ValidationError):
            PracticeApplicationPatch(legal_name="A" * 256)

    def test_patch_years_in_operation_range(self):
        from app.schemas.practice_application import PracticeApplicationPatch
        with pytest.raises(ValidationError):
            PracticeApplicationPatch(years_in_operation=-1)
        with pytest.raises(ValidationError):
            PracticeApplicationPatch(years_in_operation=201)
        patch = PracticeApplicationPatch(years_in_operation=10)
        assert patch.years_in_operation == 10

    def test_patch_multiple_fields(self):
        from app.schemas.practice_application import PracticeApplicationPatch
        patch = PracticeApplicationPatch(
            legal_name="Updated LLC",
            contact_email="updated@test.com",
            practice_management_software="Dentrix",
        )
        dumped = patch.model_dump(exclude_unset=True)
        assert len(dumped) == 3
        assert dumped["legal_name"] == "Updated LLC"


class TestPracticePatchSchema:

    def test_patch_name_only(self):
        from app.schemas.practice_application import PracticePatch
        patch = PracticePatch(name="New Practice Name")
        dumped = patch.model_dump(exclude_unset=True)
        assert dumped == {"name": "New Practice Name"}

    def test_patch_status_valid_values(self):
        from app.schemas.practice_application import PracticePatch
        patch = PracticePatch(status="ACTIVE")
        assert patch.status == "ACTIVE"
        patch2 = PracticePatch(status="INACTIVE")
        assert patch2.status == "INACTIVE"

    def test_patch_status_invalid_value(self):
        from app.schemas.practice_application import PracticePatch
        with pytest.raises(ValidationError):
            PracticePatch(status="DELETED")

    def test_patch_funding_limit(self):
        from app.schemas.practice_application import PracticePatch
        patch = PracticePatch(funding_limit_cents=500000)
        assert patch.funding_limit_cents == 500000

    def test_patch_funding_limit_negative_rejected(self):
        from app.schemas.practice_application import PracticePatch
        with pytest.raises(ValidationError):
            PracticePatch(funding_limit_cents=-100)

    def test_patch_empty_is_valid(self):
        from app.schemas.practice_application import PracticePatch
        patch = PracticePatch()
        dumped = patch.model_dump(exclude_unset=True)
        assert dumped == {}


class TestPracticeUserInviteRequestSchema:

    def test_valid_invite(self):
        from app.schemas.practice_application import PracticeUserInviteRequest
        req = PracticeUserInviteRequest(email="manager@dental.com")
        assert req.email == "manager@dental.com"
        assert req.role == "PRACTICE_MANAGER"

    def test_invalid_email_rejected(self):
        from app.schemas.practice_application import PracticeUserInviteRequest
        with pytest.raises(ValidationError):
            PracticeUserInviteRequest(email="bad-email")

    def test_invalid_role_rejected(self):
        from app.schemas.practice_application import PracticeUserInviteRequest
        with pytest.raises(ValidationError):
            PracticeUserInviteRequest(email="x@y.com", role="ADMIN")

    def test_default_role(self):
        from app.schemas.practice_application import PracticeUserInviteRequest
        req = PracticeUserInviteRequest(email="x@y.com")
        assert req.role == "PRACTICE_MANAGER"


class TestCrmEndpointPaths:

    def test_patch_application_endpoint_exists(self):
        from app.routers.applications import router
        routes = [r for r in router.routes if hasattr(r, 'path')]
        patch_route = None
        for route in routes:
            if route.path == "/internal/applications/{application_id}" and "PATCH" in route.methods:
                patch_route = route
                break
        assert patch_route is not None, "PATCH /internal/applications/{application_id} not found"

    def test_patch_practice_endpoint_exists(self):
        from app.routers.ops import router
        routes = [r for r in router.routes if hasattr(r, 'path')]
        patch_route = None
        for route in routes:
            if "/practices/" in route.path and route.path.endswith("{practice_id}") and "PATCH" in route.methods:
                patch_route = route
                break
        assert patch_route is not None, "PATCH /ops/practices/{practice_id} not found"

    def test_get_practice_users_endpoint_exists(self):
        from app.routers.ops import router
        routes = [r for r in router.routes if hasattr(r, 'path')]
        get_route = None
        for route in routes:
            if "/practices/" in route.path and route.path.endswith("/users") and "GET" in route.methods:
                get_route = route
                break
        assert get_route is not None, "GET /ops/practices/{practice_id}/users not found"

    def test_invite_practice_user_endpoint_exists(self):
        from app.routers.ops import router
        routes = [r for r in router.routes if hasattr(r, 'path')]
        post_route = None
        for route in routes:
            if "/practices/" in route.path and route.path.endswith("/users/invite") and "POST" in route.methods:
                post_route = route
                break
        assert post_route is not None, "POST /ops/practices/{practice_id}/users/invite not found"


class TestApproveConflictResponse:

    def test_409_detail_structure_in_approve(self):
        import inspect
        from app.routers.applications import _approve_application
        source = inspect.getsource(_approve_application)
        assert "HTTP_409_CONFLICT" in source
        assert "existing_practice_id" in source
        assert "existing_practice_name" in source
        assert "recommendation" in source

    def test_409_detail_structure_in_patch_application(self):
        import inspect
        from app.routers.applications import patch_application
        source = inspect.getsource(patch_application)
        assert "HTTP_409_CONFLICT" in source
        assert "existing_practice_id" in source
        assert "existing_practice_name" in source

    def test_409_detail_structure_in_invite(self):
        import inspect
        from app.routers.ops import invite_practice_user
        source = inspect.getsource(invite_practice_user)
        assert "HTTP_409_CONFLICT" in source
        assert "existing_practice_id" in source
        assert "existing_practice_name" in source


class TestAuditEventsInCrmEndpoints:

    def test_patch_application_logs_audit(self):
        import inspect
        from app.routers.applications import patch_application
        source = inspect.getsource(patch_application)
        assert "APPLICATION_UPDATED" in source
        assert "AuditService.log_event" in source

    def test_patch_practice_logs_audit(self):
        import inspect
        from app.routers.ops import patch_practice
        source = inspect.getsource(patch_practice)
        assert "PRACTICE_UPDATED" in source
        assert "AuditService.log_event" in source

    def test_invite_logs_audit(self):
        import inspect
        from app.routers.ops import invite_practice_user
        source = inspect.getsource(invite_practice_user)
        assert "PRACTICE_INVITE_CREATED" in source
        assert "AuditService.log_event" in source

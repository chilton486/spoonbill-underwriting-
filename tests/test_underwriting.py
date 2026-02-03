from app.services.underwriting import UnderwritingService
from app.models.underwriting import DecisionType
from app.models.claim import ClaimStatus


class TestUnderwritingService:
    def test_get_target_status_approve(self):
        status = UnderwritingService.get_target_status(DecisionType.APPROVE)
        assert status == ClaimStatus.APPROVED

    def test_get_target_status_decline(self):
        status = UnderwritingService.get_target_status(DecisionType.DECLINE)
        assert status == ClaimStatus.DECLINED

    def test_get_target_status_needs_review(self):
        status = UnderwritingService.get_target_status(DecisionType.NEEDS_REVIEW)
        assert status == ClaimStatus.NEEDS_REVIEW

    def test_decision_type_values(self):
        assert DecisionType.APPROVE.value == "APPROVE"
        assert DecisionType.DECLINE.value == "DECLINE"
        assert DecisionType.NEEDS_REVIEW.value == "NEEDS_REVIEW"

    def test_all_decision_types_have_target_status(self):
        for decision_type in DecisionType:
            status = UnderwritingService.get_target_status(decision_type)
            assert status in ClaimStatus

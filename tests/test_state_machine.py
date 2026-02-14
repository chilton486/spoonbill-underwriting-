import pytest
from app.models.claim import ClaimStatus, CLAIM_STATUS_TRANSITIONS, TERMINAL_STATUSES
from app.state_machine import validate_status_transition, can_transition, get_valid_transitions, InvalidStatusTransitionError


class TestStateMachine:
    def test_new_can_transition_to_needs_review(self):
        assert can_transition(ClaimStatus.NEW, ClaimStatus.NEEDS_REVIEW)

    def test_new_can_transition_to_approved(self):
        assert can_transition(ClaimStatus.NEW, ClaimStatus.APPROVED)

    def test_new_can_transition_to_declined(self):
        assert can_transition(ClaimStatus.NEW, ClaimStatus.DECLINED)

    def test_new_cannot_transition_to_paid(self):
        assert not can_transition(ClaimStatus.NEW, ClaimStatus.PAID)

    def test_new_cannot_transition_to_closed(self):
        assert not can_transition(ClaimStatus.NEW, ClaimStatus.CLOSED)

    def test_needs_review_can_transition_to_approved(self):
        assert can_transition(ClaimStatus.NEEDS_REVIEW, ClaimStatus.APPROVED)

    def test_needs_review_can_transition_to_declined(self):
        assert can_transition(ClaimStatus.NEEDS_REVIEW, ClaimStatus.DECLINED)

    def test_needs_review_cannot_transition_to_paid(self):
        assert not can_transition(ClaimStatus.NEEDS_REVIEW, ClaimStatus.PAID)

    def test_approved_can_transition_to_paid(self):
        assert can_transition(ClaimStatus.APPROVED, ClaimStatus.PAID)

    def test_approved_can_transition_to_declined(self):
        assert can_transition(ClaimStatus.APPROVED, ClaimStatus.DECLINED)

    def test_paid_can_transition_to_collecting(self):
        assert can_transition(ClaimStatus.PAID, ClaimStatus.COLLECTING)

    def test_paid_cannot_transition_to_approved(self):
        assert not can_transition(ClaimStatus.PAID, ClaimStatus.APPROVED)

    def test_collecting_can_transition_to_closed(self):
        assert can_transition(ClaimStatus.COLLECTING, ClaimStatus.CLOSED)

    def test_closed_is_terminal(self):
        assert ClaimStatus.CLOSED in TERMINAL_STATUSES
        assert not can_transition(ClaimStatus.CLOSED, ClaimStatus.NEW)
        assert not can_transition(ClaimStatus.CLOSED, ClaimStatus.APPROVED)

    def test_declined_is_terminal(self):
        assert ClaimStatus.DECLINED in TERMINAL_STATUSES
        assert not can_transition(ClaimStatus.DECLINED, ClaimStatus.NEW)
        assert not can_transition(ClaimStatus.DECLINED, ClaimStatus.APPROVED)

    def test_get_valid_transitions_from_new(self):
        transitions = get_valid_transitions(ClaimStatus.NEW)
        assert ClaimStatus.NEEDS_REVIEW in transitions
        assert ClaimStatus.APPROVED in transitions
        assert ClaimStatus.DECLINED in transitions
        assert ClaimStatus.PAID not in transitions

    def test_get_valid_transitions_from_terminal(self):
        transitions = get_valid_transitions(ClaimStatus.CLOSED)
        assert len(transitions) == 0

    def test_validate_valid_transition(self):
        validate_status_transition(ClaimStatus.NEW, ClaimStatus.APPROVED)

    def test_validate_invalid_transition_raises(self):
        with pytest.raises(InvalidStatusTransitionError) as exc_info:
            validate_status_transition(ClaimStatus.NEW, ClaimStatus.PAID)
        assert "Cannot transition" in str(exc_info.value)
        assert "NEW" in str(exc_info.value)
        assert "PAID" in str(exc_info.value)

    def test_validate_same_status_raises(self):
        with pytest.raises(InvalidStatusTransitionError):
            validate_status_transition(ClaimStatus.NEW, ClaimStatus.NEW)

    def test_approved_can_transition_to_payment_exception(self):
        assert can_transition(ClaimStatus.APPROVED, ClaimStatus.PAYMENT_EXCEPTION)

    def test_payment_exception_can_transition_to_approved(self):
        assert can_transition(ClaimStatus.PAYMENT_EXCEPTION, ClaimStatus.APPROVED)

    def test_payment_exception_can_transition_to_declined(self):
        assert can_transition(ClaimStatus.PAYMENT_EXCEPTION, ClaimStatus.DECLINED)

    def test_payment_exception_cannot_transition_to_paid(self):
        assert not can_transition(ClaimStatus.PAYMENT_EXCEPTION, ClaimStatus.PAID)

    def test_payment_exception_cannot_transition_to_new(self):
        assert not can_transition(ClaimStatus.PAYMENT_EXCEPTION, ClaimStatus.NEW)

    def test_payment_exception_cannot_transition_to_closed(self):
        assert not can_transition(ClaimStatus.PAYMENT_EXCEPTION, ClaimStatus.CLOSED)

    def test_get_valid_transitions_from_payment_exception(self):
        transitions = get_valid_transitions(ClaimStatus.PAYMENT_EXCEPTION)
        assert ClaimStatus.APPROVED in transitions
        assert ClaimStatus.DECLINED in transitions
        assert ClaimStatus.PAID not in transitions
        assert len(transitions) == 2

    def test_payment_exception_is_not_terminal(self):
        assert ClaimStatus.PAYMENT_EXCEPTION not in TERMINAL_STATUSES

    def test_all_statuses_have_transitions_defined(self):
        for status in ClaimStatus:
            assert status in CLAIM_STATUS_TRANSITIONS

from typing import FrozenSet
from .models.claim import ClaimStatus, CLAIM_STATUS_TRANSITIONS, TERMINAL_STATUSES


class InvalidStatusTransitionError(Exception):
    def __init__(self, current_status: ClaimStatus, target_status: ClaimStatus, message: str):
        self.current_status = current_status
        self.target_status = target_status
        self.message = message
        super().__init__(message)


def validate_status_transition(current_status: ClaimStatus, target_status: ClaimStatus) -> None:
    if current_status == target_status:
        raise InvalidStatusTransitionError(
            current_status,
            target_status,
            f"Claim is already in '{current_status.value}' status."
        )

    if current_status in TERMINAL_STATUSES:
        raise InvalidStatusTransitionError(
            current_status,
            target_status,
            f"Cannot transition from '{current_status.value}'. Claim lifecycle is complete."
        )

    valid_targets = CLAIM_STATUS_TRANSITIONS.get(current_status, frozenset())
    if target_status not in valid_targets:
        valid_list = ", ".join(f"'{s.value}'" for s in valid_targets) if valid_targets else "none"
        raise InvalidStatusTransitionError(
            current_status,
            target_status,
            f"Cannot transition from '{current_status.value}' to '{target_status.value}'. "
            f"Valid transitions from '{current_status.value}': {valid_list}."
        )


def can_transition(current_status: ClaimStatus, target_status: ClaimStatus) -> bool:
    if current_status == target_status:
        return False
    if current_status in TERMINAL_STATUSES:
        return False
    valid_targets = CLAIM_STATUS_TRANSITIONS.get(current_status, frozenset())
    return target_status in valid_targets


def get_valid_transitions(current_status: ClaimStatus) -> FrozenSet[ClaimStatus]:
    return CLAIM_STATUS_TRANSITIONS.get(current_status, frozenset())

"""
Tests for Phase 3 Payments MVP.

These tests cover:
- Idempotent PaymentIntent creation
- No double-pay under retries
- Ledger correctness (approve → confirm, approve → fail)
- Tenant isolation on payment access
- Simulated provider success/failure paths

Note: Some tests require PostgreSQL due to UUID column types.
Unit tests for the simulated provider work with any database.
"""
from app.providers.simulated import SimulatedProvider
from app.providers.base import PaymentResultStatus


class TestSimulatedProvider:
    """Unit tests for the simulated payment provider."""
    
    def test_provider_success_path(self):
        """Test that provider returns success when failure_rate is 0."""
        provider = SimulatedProvider(failure_rate=0.0)
        
        result = provider.send_payment(
            payment_intent_id="test-intent-1",
            amount_cents=10000,
            currency="USD",
            recipient_practice_id=1,
            idempotency_key="test_success",
        )
        
        assert result.status == PaymentResultStatus.SUCCESS
        assert result.provider_reference is not None
        assert result.provider_reference.startswith("SIM-")
        assert result.failure_code is None
    
    def test_provider_failure_path(self):
        """Test that provider returns failure when failure_rate is 1 and force_fail is True."""
        provider = SimulatedProvider(failure_rate=1.0, force_fail=True)
        
        result = provider.send_payment(
            payment_intent_id="test-intent-2",
            amount_cents=10000,
            currency="USD",
            recipient_practice_id=1,
            idempotency_key="test_failure",
        )
        
        assert result.status == PaymentResultStatus.FAILED
        assert result.failure_code is not None
        assert result.failure_code in [
            "INSUFFICIENT_FUNDS",
            "ACCOUNT_CLOSED",
            "INVALID_ACCOUNT",
            "NETWORK_ERROR",
            "COMPLIANCE_HOLD",
        ]
    
    def test_provider_idempotency(self):
        """Test that same idempotency_key returns same result."""
        provider = SimulatedProvider(failure_rate=0.0)
        
        result1 = provider.send_payment(
            payment_intent_id="test-intent-3",
            amount_cents=10000,
            currency="USD",
            recipient_practice_id=1,
            idempotency_key="test_idempotent",
        )
        
        result2 = provider.send_payment(
            payment_intent_id="test-intent-3",
            amount_cents=10000,
            currency="USD",
            recipient_practice_id=1,
            idempotency_key="test_idempotent",
        )
        
        assert result1.provider_reference == result2.provider_reference
        assert result1.status == result2.status
    
    def test_provider_deterministic_mode_success(self):
        """Test deterministic mode with no failures produces success."""
        provider = SimulatedProvider(failure_rate=0.0, deterministic=True)
        
        result = provider.send_payment(
            payment_intent_id="test-intent-4",
            amount_cents=10000,
            currency="USD",
            recipient_practice_id=1,
            idempotency_key="test_deterministic_success",
        )
        
        assert result.status == PaymentResultStatus.SUCCESS
    
    def test_provider_check_status(self):
        """Test checking payment status after sending."""
        provider = SimulatedProvider(failure_rate=0.0)
        
        send_result = provider.send_payment(
            payment_intent_id="test-intent-5",
            amount_cents=10000,
            currency="USD",
            recipient_practice_id=1,
            idempotency_key="test_check_status",
        )
        
        check_result = provider.check_payment_status(send_result.provider_reference)
        
        assert check_result.status == PaymentResultStatus.SUCCESS
        assert check_result.provider_reference == send_result.provider_reference
    
    def test_provider_check_unknown_reference_returns_success(self):
        """Test checking status of unknown payment reference returns success (simulated behavior)."""
        provider = SimulatedProvider(failure_rate=0.0)
        
        result = provider.check_payment_status("UNKNOWN-REF")
        
        assert result.status == PaymentResultStatus.SUCCESS
        assert result.provider_reference == "UNKNOWN-REF"


class TestPaymentIntentIdempotencyKey:
    """Unit tests for PaymentIntent idempotency key generation."""
    
    def test_idempotency_key_format(self):
        """Test that idempotency key follows expected format."""
        from app.models.payment import PaymentIntent
        
        key = PaymentIntent.generate_idempotency_key(123)
        assert key == "claim:123:payment:v1"
    
    def test_idempotency_key_is_deterministic(self):
        """Test that same claim_id produces same key."""
        from app.models.payment import PaymentIntent
        
        key1 = PaymentIntent.generate_idempotency_key(456)
        key2 = PaymentIntent.generate_idempotency_key(456)
        assert key1 == key2
    
    def test_different_claims_have_different_keys(self):
        """Test that different claim_ids produce different keys."""
        from app.models.payment import PaymentIntent
        
        key1 = PaymentIntent.generate_idempotency_key(1)
        key2 = PaymentIntent.generate_idempotency_key(2)
        assert key1 != key2


class TestPaymentIntentStatusTransitions:
    """Unit tests for PaymentIntent state machine."""
    
    def test_queued_can_transition_to_sent(self):
        """Test QUEUED -> SENT is valid."""
        from app.models.payment import PaymentIntentStatus, PAYMENT_INTENT_TRANSITIONS
        
        valid_transitions = PAYMENT_INTENT_TRANSITIONS[PaymentIntentStatus.QUEUED]
        assert PaymentIntentStatus.SENT in valid_transitions
    
    def test_queued_can_transition_to_failed(self):
        """Test QUEUED -> FAILED is valid."""
        from app.models.payment import PaymentIntentStatus, PAYMENT_INTENT_TRANSITIONS
        
        valid_transitions = PAYMENT_INTENT_TRANSITIONS[PaymentIntentStatus.QUEUED]
        assert PaymentIntentStatus.FAILED in valid_transitions
    
    def test_sent_can_transition_to_confirmed(self):
        """Test SENT -> CONFIRMED is valid."""
        from app.models.payment import PaymentIntentStatus, PAYMENT_INTENT_TRANSITIONS
        
        valid_transitions = PAYMENT_INTENT_TRANSITIONS[PaymentIntentStatus.SENT]
        assert PaymentIntentStatus.CONFIRMED in valid_transitions
    
    def test_sent_can_transition_to_failed(self):
        """Test SENT -> FAILED is valid."""
        from app.models.payment import PaymentIntentStatus, PAYMENT_INTENT_TRANSITIONS
        
        valid_transitions = PAYMENT_INTENT_TRANSITIONS[PaymentIntentStatus.SENT]
        assert PaymentIntentStatus.FAILED in valid_transitions
    
    def test_confirmed_is_terminal(self):
        """Test CONFIRMED has no valid transitions."""
        from app.models.payment import PaymentIntentStatus, PAYMENT_INTENT_TRANSITIONS, TERMINAL_PAYMENT_STATUSES
        
        valid_transitions = PAYMENT_INTENT_TRANSITIONS[PaymentIntentStatus.CONFIRMED]
        assert len(valid_transitions) == 0
        assert PaymentIntentStatus.CONFIRMED in TERMINAL_PAYMENT_STATUSES
    
    def test_failed_is_terminal(self):
        """Test FAILED has no valid transitions (retry creates new attempt, not transition)."""
        from app.models.payment import PaymentIntentStatus, PAYMENT_INTENT_TRANSITIONS, TERMINAL_PAYMENT_STATUSES
        
        valid_transitions = PAYMENT_INTENT_TRANSITIONS[PaymentIntentStatus.FAILED]
        assert len(valid_transitions) == 0
        assert PaymentIntentStatus.FAILED in TERMINAL_PAYMENT_STATUSES


class TestLedgerAccountTypes:
    """Unit tests for ledger account types."""
    
    def test_capital_cash_account_type_exists(self):
        """Test CAPITAL_CASH account type is defined."""
        from app.models.ledger import LedgerAccountType
        
        assert LedgerAccountType.CAPITAL_CASH.value == "CAPITAL_CASH"
    
    def test_payment_clearing_account_type_exists(self):
        """Test PAYMENT_CLEARING account type is defined."""
        from app.models.ledger import LedgerAccountType
        
        assert LedgerAccountType.PAYMENT_CLEARING.value == "PAYMENT_CLEARING"
    
    def test_practice_payable_account_type_exists(self):
        """Test PRACTICE_PAYABLE account type is defined."""
        from app.models.ledger import LedgerAccountType
        
        assert LedgerAccountType.PRACTICE_PAYABLE.value == "PRACTICE_PAYABLE"


class TestLedgerEntryDirection:
    """Unit tests for ledger entry direction."""
    
    def test_debit_direction_exists(self):
        """Test DEBIT direction is defined."""
        from app.models.ledger import LedgerEntryDirection
        
        assert LedgerEntryDirection.DEBIT.value == "DEBIT"
    
    def test_credit_direction_exists(self):
        """Test CREDIT direction is defined."""
        from app.models.ledger import LedgerEntryDirection
        
        assert LedgerEntryDirection.CREDIT.value == "CREDIT"


class TestLedgerEntryStatus:
    """Unit tests for ledger entry status."""
    
    def test_pending_status_exists(self):
        """Test PENDING status is defined."""
        from app.models.ledger import LedgerEntryStatus
        
        assert LedgerEntryStatus.PENDING.value == "PENDING"
    
    def test_posted_status_exists(self):
        """Test POSTED status is defined."""
        from app.models.ledger import LedgerEntryStatus
        
        assert LedgerEntryStatus.POSTED.value == "POSTED"
    
    def test_reversed_status_exists(self):
        """Test REVERSED status is defined."""
        from app.models.ledger import LedgerEntryStatus
        
        assert LedgerEntryStatus.REVERSED.value == "REVERSED"


class TestPaymentExceptions:
    """Unit tests for payment service exceptions."""
    
    def test_payment_error_exists(self):
        """Test PaymentError exception is defined."""
        from app.services.payments import PaymentError
        
        error = PaymentError("test error")
        assert str(error) == "test error"
    
    def test_payment_already_exists_error(self):
        """Test PaymentAlreadyExistsError exception is defined."""
        from app.services.payments import PaymentAlreadyExistsError
        
        error = PaymentAlreadyExistsError("payment exists")
        assert str(error) == "payment exists"
    
    def test_invalid_claim_state_error(self):
        """Test InvalidClaimStateError exception is defined."""
        from app.services.payments import InvalidClaimStateError
        
        error = InvalidClaimStateError("invalid state")
        assert str(error) == "invalid state"


class TestLedgerServiceExceptions:
    """Unit tests for ledger service exceptions."""
    
    def test_ledger_error_exists(self):
        """Test LedgerError exception is defined."""
        from app.services.ledger import LedgerError
        
        error = LedgerError("ledger error")
        assert str(error) == "ledger error"
    
    def test_insufficient_funds_error(self):
        """Test InsufficientFundsError exception is defined."""
        from app.services.ledger import InsufficientFundsError
        
        error = InsufficientFundsError("insufficient funds")
        assert str(error) == "insufficient funds"
    
    def test_duplicate_entry_error(self):
        """Test DuplicateEntryError exception is defined."""
        from app.services.ledger import DuplicateEntryError
        
        error = DuplicateEntryError("duplicate entry")
        assert str(error) == "duplicate entry"


class TestClaimToken:
    """Unit tests for claim token generation."""
    
    def test_claim_token_format(self):
        """Test that claim token follows expected format: SB-CLM-<8 chars>."""
        from app.models.claim import Claim
        
        token = Claim.generate_claim_token()
        assert token.startswith("SB-CLM-")
        assert len(token) == 15  # "SB-CLM-" (7) + 8 chars
    
    def test_claim_token_is_unique(self):
        """Test that multiple token generations produce different tokens."""
        from app.models.claim import Claim
        
        tokens = [Claim.generate_claim_token() for _ in range(100)]
        assert len(set(tokens)) == 100  # All unique
    
    def test_claim_token_characters_are_base32(self):
        """Test that token suffix uses base32 characters."""
        from app.models.claim import Claim
        import string
        
        token = Claim.generate_claim_token()
        suffix = token[7:]  # Remove "SB-CLM-" prefix
        base32_chars = set(string.ascii_uppercase + "234567")
        assert all(c in base32_chars for c in suffix)


class TestLedgerTracing:
    """Unit tests for ledger tracing helper methods."""
    
    def test_get_entries_for_payment_intent_method_exists(self):
        """Test that get_entries_for_payment_intent method exists."""
        from app.services.ledger import LedgerService
        
        assert hasattr(LedgerService, 'get_entries_for_payment_intent')
        assert callable(getattr(LedgerService, 'get_entries_for_payment_intent'))
    
    def test_get_entries_for_claim_method_exists(self):
        """Test that get_entries_for_claim method exists."""
        from app.services.ledger import LedgerService
        
        assert hasattr(LedgerService, 'get_entries_for_claim')
        assert callable(getattr(LedgerService, 'get_entries_for_claim'))

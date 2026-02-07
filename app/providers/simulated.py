import uuid
import random
import logging
from typing import Dict

from .base import PaymentProviderBase, PaymentResult, PaymentResultStatus

logger = logging.getLogger(__name__)


class SimulatedProvider(PaymentProviderBase):
    _payments: Dict[str, PaymentResult] = {}
    
    FAILURE_RATE = 0.1
    
    FAILURE_CODES = [
        ("INSUFFICIENT_FUNDS", "Recipient account has insufficient funds"),
        ("ACCOUNT_CLOSED", "Recipient account is closed"),
        ("INVALID_ACCOUNT", "Invalid recipient account number"),
        ("NETWORK_ERROR", "Network timeout during payment processing"),
        ("COMPLIANCE_HOLD", "Payment held for compliance review"),
    ]

    def __init__(self, failure_rate: float = 0.1, deterministic: bool = False, force_fail: bool = False):
        self.failure_rate = failure_rate
        self.deterministic = deterministic
        self.force_fail = force_fail

    def send_payment(
        self,
        payment_intent_id: str,
        amount_cents: int,
        currency: str,
        recipient_practice_id: int,
        idempotency_key: str,
    ) -> PaymentResult:
        if idempotency_key in self._payments:
            logger.info(f"Returning cached result for idempotency_key={idempotency_key}")
            return self._payments[idempotency_key]
        
        provider_reference = f"SIM-{uuid.uuid4().hex[:12].upper()}"
        
        should_fail = self.force_fail
        if not self.deterministic and not should_fail:
            should_fail = random.random() < self.failure_rate
        
        if should_fail:
            failure_code, failure_message = random.choice(self.FAILURE_CODES)
            result = PaymentResult(
                status=PaymentResultStatus.FAILED,
                provider_reference=provider_reference,
                failure_code=failure_code,
                failure_message=failure_message,
            )
            logger.warning(
                f"Simulated payment FAILED: intent={payment_intent_id}, "
                f"amount={amount_cents}, code={failure_code}"
            )
        else:
            result = PaymentResult(
                status=PaymentResultStatus.SUCCESS,
                provider_reference=provider_reference,
            )
            logger.info(
                f"Simulated payment SUCCESS: intent={payment_intent_id}, "
                f"amount={amount_cents}, ref={provider_reference}"
            )
        
        self._payments[idempotency_key] = result
        return result

    def check_payment_status(self, provider_reference: str) -> PaymentResult:
        for result in self._payments.values():
            if result.provider_reference == provider_reference:
                return result
        
        return PaymentResult(
            status=PaymentResultStatus.SUCCESS,
            provider_reference=provider_reference,
        )

    def reset(self) -> None:
        self._payments.clear()
        logger.info("Simulated provider state reset")

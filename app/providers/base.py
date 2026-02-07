from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from enum import Enum


class PaymentResultStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PENDING = "PENDING"


@dataclass
class PaymentResult:
    status: PaymentResultStatus
    provider_reference: Optional[str] = None
    failure_code: Optional[str] = None
    failure_message: Optional[str] = None


class PaymentProviderBase(ABC):
    @abstractmethod
    def send_payment(
        self,
        payment_intent_id: str,
        amount_cents: int,
        currency: str,
        recipient_practice_id: int,
        idempotency_key: str,
    ) -> PaymentResult:
        pass

    @abstractmethod
    def check_payment_status(self, provider_reference: str) -> PaymentResult:
        pass

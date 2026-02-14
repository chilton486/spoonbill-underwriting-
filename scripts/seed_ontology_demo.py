"""Seed demo data for ontology testing.

Run: python -m scripts.seed_ontology_demo

Creates a practice with multiple payers, CDT codes, varied timestamps,
some denials, and some confirmed payments — enough to produce meaningful
ontology metrics.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
import random

from app.database import SessionLocal
from app.models.practice import Practice
from app.models.user import User, UserRole
from app.models.claim import Claim, ClaimStatus
from app.models.payment import PaymentIntent, PaymentIntentStatus, PaymentProvider
from app.services.auth import AuthService

PAYERS = ["Delta Dental", "Cigna Dental", "MetLife", "Aetna Dental", "Guardian", "Medicaid State", "Self Pay"]
CDT_CODES = ["D0120", "D0274", "D1110", "D2150", "D2740", "D4341", "D7210", "D0330", "D2391", "D4910"]
PATIENT_NAMES = [
    "Alice Johnson", "Bob Smith", "Carol Davis", "David Wilson", "Eva Martinez",
    "Frank Brown", "Grace Lee", "Henry Taylor", "Irene Anderson", "Jack Thomas",
    "Karen White", "Leo Harris", "Maria Clark", "Nathan Lewis", "Olivia Walker",
]
STATUSES_WITH_WEIGHTS = [
    (ClaimStatus.APPROVED.value, 8),
    (ClaimStatus.PAID.value, 5),
    (ClaimStatus.DECLINED.value, 2),
    (ClaimStatus.CLOSED.value, 3),
    (ClaimStatus.NEEDS_REVIEW.value, 1),
    (ClaimStatus.PAYMENT_EXCEPTION.value, 1),
]


def weighted_choice(items):
    total = sum(w for _, w in items)
    r = random.random() * total
    cum = 0
    for item, weight in items:
        cum += weight
        if r <= cum:
            return item
    return items[-1][0]


def main():
    db = SessionLocal()
    try:
        practice = db.query(Practice).first()
        if not practice:
            practice = Practice(
                name="Ontology Demo Practice",
                status="ACTIVE",
                funding_limit_cents=500_000_00,
            )
            db.add(practice)
            db.flush()
            print(f"Created practice: {practice.name} (id={practice.id})")
        else:
            practice.funding_limit_cents = 500_000_00
            db.flush()
            print(f"Using existing practice: {practice.name} (id={practice.id})")

        user = db.query(User).filter(User.practice_id == practice.id, User.role == UserRole.PRACTICE_MANAGER.value).first()
        if not user:
            user = User(
                email="ontology-demo@spoonbill.com",
                password_hash=AuthService.get_password_hash("demo123"),
                role=UserRole.PRACTICE_MANAGER.value,
                practice_id=practice.id,
                is_active=True,
            )
            db.add(user)
            db.flush()
            print(f"Created user: {user.email}")
        else:
            print(f"Using existing user: {user.email}")

        random.seed(42)
        now = datetime.utcnow()

        for i in range(40):
            payer = random.choice(PAYERS)
            codes = ",".join(random.sample(CDT_CODES, random.randint(1, 3)))
            amount = random.randint(5000, 250000)
            status = weighted_choice(STATUSES_WITH_WEIGHTS)
            created = now - timedelta(days=random.randint(1, 120), hours=random.randint(0, 23))
            patient_name = random.choice(PATIENT_NAMES)

            claim = Claim(
                practice_id=practice.id,
                patient_name=patient_name,
                payer=payer,
                amount_cents=amount,
                procedure_date=(created - timedelta(days=random.randint(1, 7))).date(),
                procedure_codes=codes,
                status=status,
                claim_token=Claim.generate_claim_token(),
                fingerprint=f"demo-ontology-{practice.id}-{i}",
                created_at=created,
                updated_at=created,
                payment_exception=(status == ClaimStatus.PAYMENT_EXCEPTION.value),
            )
            db.add(claim)
            db.flush()

            if status in (ClaimStatus.APPROVED.value, ClaimStatus.PAID.value, ClaimStatus.CLOSED.value):
                sent_at = created + timedelta(hours=random.randint(1, 48))
                confirmed_at = sent_at + timedelta(hours=random.randint(2, 72)) if status in (ClaimStatus.PAID.value, ClaimStatus.CLOSED.value) else None
                pi_status = PaymentIntentStatus.CONFIRMED.value if confirmed_at else PaymentIntentStatus.SENT.value

                pi = PaymentIntent(
                    claim_id=claim.id,
                    practice_id=practice.id,
                    amount_cents=amount,
                    currency="USD",
                    status=pi_status,
                    idempotency_key=f"demo-onto-{practice.id}-{claim.id}",
                    provider=PaymentProvider.SIMULATED.value,
                    sent_at=sent_at,
                    confirmed_at=confirmed_at,
                    created_at=created,
                    updated_at=sent_at,
                )
                db.add(pi)

            if status == ClaimStatus.PAYMENT_EXCEPTION.value:
                pi = PaymentIntent(
                    claim_id=claim.id,
                    practice_id=practice.id,
                    amount_cents=amount,
                    currency="USD",
                    status=PaymentIntentStatus.FAILED.value,
                    idempotency_key=f"demo-onto-{practice.id}-{claim.id}",
                    provider=PaymentProvider.SIMULATED.value,
                    failure_code="INSUFFICIENT_FUNDS",
                    failure_message="Simulated failure for demo",
                    sent_at=created + timedelta(hours=1),
                    created_at=created,
                    updated_at=created,
                )
                db.add(pi)

        db.commit()
        print(f"Seeded 40 claims with payments for practice {practice.id}")
        print(f"Login: ontology-demo@spoonbill.com / demo123")

    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

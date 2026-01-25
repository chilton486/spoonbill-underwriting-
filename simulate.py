from __future__ import annotations

from datetime import date, timedelta

from sqlmodel import select

from app.db import init_db, session_scope
from app.ledger import fund_claim_atomic, settle_claim_atomic
from app.models import CapitalPool, Claim, Practice
from app.underwriting import UnderwritingPolicy, underwrite_claim


def policy() -> UnderwritingPolicy:
    return UnderwritingPolicy(
        approved_payers={"Aetna", "UnitedHealthcare", "BCBS", "Cigna"},
        excluded_plan_keywords={"medicaid", "capitation", "carve-out"},
        procedure_pay_rate_threshold=0.90,
        min_practice_tenure_months=12,
        min_practice_clean_claim_rate=0.90,
        procedure_historical_pay_rate={
            "99213": 0.95,
            "99214": 0.93,
            "93000": 0.91,
            "12345": 0.85,
        },
    )


def main() -> None:
    init_db()

    with session_scope() as session:
        pool = session.exec(select(CapitalPool).where(CapitalPool.id == "POOL")).first()
        if pool is None:
            pool = CapitalPool(id="POOL", total_capital=1_000_000, available_capital=1_000_000)
            session.add(pool)

        practice = session.exec(select(Practice).where(Practice.id == "PRACTICE_1")).first()
        if practice is None:
            practice = Practice(
                id="PRACTICE_1",
                tenure_months=18,
                historical_clean_claim_rate=0.96,
                payer_mix="Aetna:0.5;UHC:0.5",
                max_exposure_limit=50_000,
                current_exposure=0,
            )
            session.add(practice)

        claim = session.exec(select(Claim).where(Claim.claim_id == "CLM_1")).first()
        if claim is None:
            claim = Claim(
                claim_id="CLM_1",
                practice_id=practice.id,
                payer="Aetna",
                procedure_code="99213",
                billed_amount=250,
                expected_allowed_amount=180,
                submission_date=date.today(),
            )
            session.add(claim)

    with session_scope() as session:
        pool = session.exec(select(CapitalPool).where(CapitalPool.id == "POOL")).one()
        claim = session.exec(select(Claim).where(Claim.claim_id == "CLM_1")).one()
        practice = session.exec(select(Practice).where(Practice.id == claim.practice_id)).one()

        remaining = max(0, practice.max_exposure_limit - practice.current_exposure)
        decision = underwrite_claim(
            claim=claim,
            practice=practice,
            policy=policy(),
            remaining_practice_exposure_limit=remaining,
            pool_available_capital=pool.available_capital,
        )
        print("UNDERWRITE:", decision)

        if decision.approved:
            fund_claim_atomic(session=session, pool_id=pool.id, claim_id=claim.claim_id, funded_amount=decision.funded_amount)
        else:
            claim.decline_reason_code = decision.reason_code
            session.add(claim)

    with session_scope() as session:
        settlement_date = date.today() + timedelta(days=14)
        settle_claim_atomic(
            session=session,
            pool_id="POOL",
            claim_id="CLM_1",
            settlement_date=settlement_date,
            settlement_amount=180,
        )

    with session_scope() as session:
        pool = session.exec(select(CapitalPool).where(CapitalPool.id == "POOL")).one()
        practice = session.exec(select(Practice).where(Practice.id == "PRACTICE_1")).one()
        claim = session.exec(select(Claim).where(Claim.claim_id == "CLM_1")).one()

        print("POOL:", pool)
        print("PRACTICE:", practice)
        print("CLAIM:", claim)


if __name__ == "__main__":
    main()

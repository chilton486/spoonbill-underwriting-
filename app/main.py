from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlmodel import select

from .db import init_db, session_scope
from .ledger import fund_claim_atomic, settle_claim_atomic
from .models import CapitalPool, Claim, ClaimStatus, Practice
from .underwriting import UnderwritingPolicy, underwrite_claim


app = FastAPI(title="Spoonbill Underwriting & Capital Allocation (V1)")


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"] ,
)


@app.on_event("startup")
def _startup() -> None:
    init_db()


class CreatePracticeRequest(BaseModel):
    id: str
    tenure_months: int
    historical_clean_claim_rate: float
    payer_mix: str
    max_exposure_limit: int


class CreateClaimRequest(BaseModel):
    claim_id: str
    practice_id: str
    payer: str
    procedure_code: str
    billed_amount: int
    expected_allowed_amount: int
    submission_date: date


class UnderwriteRequest(BaseModel):
    pool_id: str


class FundRequest(BaseModel):
    pool_id: str


class SettleRequest(BaseModel):
    pool_id: str
    settlement_date: date
    settlement_amount: int


class SimulateRequest(BaseModel):
    pool_id: str = "POOL"

    # If true, ensure demo data exists (pool + practices + claims).
    seed_if_empty: bool = True

    # Advance the lifecycle by one step for all claims.
    # submitted -> underwriting -> funded -> reimbursed
    advance_one_step: bool = True


def _default_policy() -> UnderwritingPolicy:
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


@app.post("/capital-pool/init")
def init_pool(total_capital: int, pool_id: str = "POOL") -> CapitalPool:
    with session_scope() as session:
        existing = session.exec(select(CapitalPool).where(CapitalPool.id == pool_id)).first()
        if existing is not None:
            return existing
        pool = CapitalPool(id=pool_id, total_capital=total_capital, available_capital=total_capital)
        session.add(pool)
        session.flush()
        return pool


@app.get("/capital-pool/{pool_id}")
def get_pool(pool_id: str) -> CapitalPool:
    with session_scope() as session:
        pool = session.exec(select(CapitalPool).where(CapitalPool.id == pool_id)).first()
        if pool is None:
            raise HTTPException(status_code=404, detail="Capital pool not found")
        return pool


@app.get("/claims")
def list_claims(practice_id: Optional[str] = None) -> list[Claim]:
    with session_scope() as session:
        stmt = select(Claim)
        if practice_id is not None:
            stmt = stmt.where(Claim.practice_id == practice_id)
        return session.exec(stmt).all()


@app.get("/practices")
def list_practices() -> list[Practice]:
    with session_scope() as session:
        return session.exec(select(Practice)).all()


@app.post("/practices")
def create_practice(req: CreatePracticeRequest) -> Practice:
    with session_scope() as session:
        practice = Practice(
            id=req.id,
            tenure_months=req.tenure_months,
            historical_clean_claim_rate=req.historical_clean_claim_rate,
            payer_mix=req.payer_mix,
            max_exposure_limit=req.max_exposure_limit,
        )
        session.add(practice)
        session.flush()
        return practice


@app.post("/claims")
def create_claim(req: CreateClaimRequest) -> Claim:
    with session_scope() as session:
        practice = session.exec(select(Practice).where(Practice.id == req.practice_id)).first()
        if practice is None:
            raise HTTPException(status_code=404, detail="Practice not found")

        claim = Claim(
            claim_id=req.claim_id,
            practice_id=req.practice_id,
            payer=req.payer,
            procedure_code=req.procedure_code,
            billed_amount=req.billed_amount,
            expected_allowed_amount=req.expected_allowed_amount,
            submission_date=req.submission_date,
        )
        session.add(claim)
        session.flush()
        return claim


@app.post("/claims/{claim_id}/underwrite")
def underwrite(claim_id: str, req: UnderwriteRequest) -> dict:
    with session_scope() as session:
        claim = session.exec(select(Claim).where(Claim.claim_id == claim_id)).first()
        if claim is None:
            raise HTTPException(status_code=404, detail="Claim not found")
        practice = session.exec(select(Practice).where(Practice.id == claim.practice_id)).one()
        pool = session.exec(select(CapitalPool).where(CapitalPool.id == req.pool_id)).one()

        remaining = practice.max_exposure_limit - practice.current_exposure
        decision = underwrite_claim(
            claim=claim,
            practice=practice,
            policy=_default_policy(),
            remaining_practice_exposure_limit=max(0, remaining),
            pool_available_capital=pool.available_capital,
        )

        if not decision.approved:
            claim.decline_reason_code = decision.reason_code
            session.add(claim)
        else:
            claim.status = ClaimStatus.underwriting
            session.add(claim)

        return {
            "approved": decision.approved,
            "funded_amount": decision.funded_amount,
            "reason_code": decision.reason_code,
        }


@app.post("/claims/{claim_id}/fund")
def fund(claim_id: str, req: FundRequest) -> Claim:
    with session_scope() as session:
        claim = session.exec(select(Claim).where(Claim.claim_id == claim_id)).first()
        if claim is None:
            raise HTTPException(status_code=404, detail="Claim not found")
        practice = session.exec(select(Practice).where(Practice.id == claim.practice_id)).one()
        pool = session.exec(select(CapitalPool).where(CapitalPool.id == req.pool_id)).one()

        remaining = max(0, practice.max_exposure_limit - practice.current_exposure)
        decision = underwrite_claim(
            claim=claim,
            practice=practice,
            policy=_default_policy(),
            remaining_practice_exposure_limit=remaining,
            pool_available_capital=pool.available_capital,
        )
        if not decision.approved:
            claim.decline_reason_code = decision.reason_code
            session.add(claim)
            raise HTTPException(status_code=400, detail={"reason_code": decision.reason_code})

        fund_claim_atomic(
            session=session,
            pool_id=req.pool_id,
            claim_id=claim_id,
            funded_amount=decision.funded_amount,
        )
        session.flush()
        return session.exec(select(Claim).where(Claim.claim_id == claim_id)).one()


@app.post("/simulate")
def simulate(req: SimulateRequest) -> dict:
    """Demo helper.

    - Seeds a pool, practices, and a few claims if empty.
    - Optionally advances all claims one step through the lifecycle.
    """

    with session_scope() as session:
        pool = session.exec(select(CapitalPool).where(CapitalPool.id == req.pool_id)).first()
        if pool is None and req.seed_if_empty:
            pool = CapitalPool(id=req.pool_id, total_capital=1_000_000, available_capital=1_000_000)
            session.add(pool)

        practices = session.exec(select(Practice)).all()
        claims = session.exec(select(Claim)).all()

        if req.seed_if_empty and len(practices) == 0:
            session.add(
                Practice(
                    id="Sunrise Family Medicine",
                    tenure_months=24,
                    historical_clean_claim_rate=0.96,
                    payer_mix="Aetna:0.4;UnitedHealthcare:0.3;BCBS:0.3",
                    max_exposure_limit=100_000,
                    current_exposure=0,
                )
            )
            session.add(
                Practice(
                    id="Riverside Cardiology",
                    tenure_months=18,
                    historical_clean_claim_rate=0.94,
                    payer_mix="BCBS:0.6;Cigna:0.4",
                    max_exposure_limit=150_000,
                    current_exposure=0,
                )
            )

        claims = session.exec(select(Claim)).all()
        if req.seed_if_empty and len(claims) == 0:
            session.add(
                Claim(
                    claim_id="CLM-1001",
                    practice_id="Sunrise Family Medicine",
                    payer="Aetna",
                    procedure_code="99213",
                    billed_amount=250,
                    expected_allowed_amount=180,
                    submission_date=date.today(),
                )
            )
            session.add(
                Claim(
                    claim_id="CLM-1002",
                    practice_id="Sunrise Family Medicine",
                    payer="UnitedHealthcare",
                    procedure_code="99214",
                    billed_amount=420,
                    expected_allowed_amount=300,
                    submission_date=date.today(),
                )
            )
            session.add(
                Claim(
                    claim_id="CLM-2001",
                    practice_id="Riverside Cardiology",
                    payer="BCBS",
                    procedure_code="93000",
                    billed_amount=560,
                    expected_allowed_amount=400,
                    submission_date=date.today(),
                )
            )

        session.flush()

    if not req.advance_one_step:
        return get_state(pool_id=req.pool_id)

    with session_scope() as session:
        pool = session.exec(select(CapitalPool).where(CapitalPool.id == req.pool_id)).one()
        claims = session.exec(select(Claim)).all()

        for claim in claims:
            if claim.status == ClaimStatus.submitted:
                claim.status = ClaimStatus.underwriting
                session.add(claim)
                continue

            if claim.status == ClaimStatus.underwriting:
                try:
                    fund_claim_atomic(
                        session=session,
                        pool_id=req.pool_id,
                        claim_id=claim.claim_id,
                        funded_amount=claim.expected_allowed_amount,
                    )
                except Exception:
                    claim.status = ClaimStatus.exception
                    session.add(claim)
                continue

            if claim.status == ClaimStatus.funded:
                settle_claim_atomic(
                    session=session,
                    pool_id=req.pool_id,
                    claim_id=claim.claim_id,
                    settlement_date=date.today(),
                    settlement_amount=claim.funded_amount,
                )

        session.flush()

    return get_state(pool_id=req.pool_id)


@app.post("/claims/{claim_id}/settle")
def settle(claim_id: str, req: SettleRequest) -> Claim:
    with session_scope() as session:
        claim = session.exec(select(Claim).where(Claim.claim_id == claim_id)).first()
        if claim is None:
            raise HTTPException(status_code=404, detail="Claim not found")

        settle_claim_atomic(
            session=session,
            pool_id=req.pool_id,
            claim_id=claim_id,
            settlement_date=req.settlement_date,
            settlement_amount=req.settlement_amount,
        )
        session.flush()
        return session.exec(select(Claim).where(Claim.claim_id == claim_id)).one()


@app.get("/state")
def get_state(pool_id: str = "POOL", practice_id: Optional[str] = None) -> dict:
    with session_scope() as session:
        pool = session.exec(select(CapitalPool).where(CapitalPool.id == pool_id)).first()
        practices = session.exec(select(Practice)).all()
        claims = session.exec(select(Claim)).all()

        if practice_id is not None:
            practices = [p for p in practices if p.id == practice_id]
            claims = [c for c in claims if c.practice_id == practice_id]

        return {
            "pool": pool.model_dump() if pool else None,
            "practices": [p.model_dump() for p in practices],
            "claims": [c.model_dump() for c in claims],
        }

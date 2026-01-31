from __future__ import annotations

import json
import logging
import uuid
from datetime import date
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from sqlmodel import select

from .db import init_db, session_scope
from .ledger import LedgerError, fund_claim_atomic, settle_claim_atomic
from .models import (
    AdjudicationStatus,
    CapitalPool,
    Claim,
    ClaimStatus,
    InvalidStatusTransitionError,
    Practice,
    get_valid_transitions,
    validate_status_transition,
)
from .underwriting import UnderwritingPolicy, underwrite_claim

logger = logging.getLogger(__name__)

app = FastAPI(title="Spoonbill Underwriting & Capital Allocation (V1)")


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


class ResetDemoRequest(BaseModel):
    pool_id: str = "POOL"


class ClaimSubmitRequest(BaseModel):
    practice_npi: Optional[str] = None
    practice_id: Optional[str] = None
    payer: str
    procedure_codes: list[str]
    billed_amount: float
    expected_allowed_amount: float
    service_date: date
    external_claim_id: str

    @field_validator("practice_npi")
    @classmethod
    def practice_npi_strip(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v:
                return None
        return v

    @field_validator("practice_id")
    @classmethod
    def practice_id_strip(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v:
                return None
        return v

    @field_validator("payer")
    @classmethod
    def payer_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("payer cannot be empty")
        return v.strip()

    @field_validator("procedure_codes")
    @classmethod
    def procedure_codes_not_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("procedure_codes cannot be empty")
        cleaned = [code.strip() for code in v if code.strip()]
        if not cleaned:
            raise ValueError("procedure_codes must contain at least one valid code")
        return cleaned

    @field_validator("billed_amount")
    @classmethod
    def billed_amount_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("billed_amount must be positive")
        return v

    @field_validator("expected_allowed_amount")
    @classmethod
    def expected_allowed_amount_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("expected_allowed_amount must be positive")
        return v

    @field_validator("external_claim_id")
    @classmethod
    def external_claim_id_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("external_claim_id cannot be empty")
        return v.strip()


class ClearinghouseWebhookRequest(BaseModel):
    external_claim_id: str
    status: Literal["approved", "denied"]
    approved_amount: Optional[float] = None
    reason_codes: Optional[list[str]] = None

    @field_validator("external_claim_id")
    @classmethod
    def external_claim_id_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("external_claim_id cannot be empty")
        return v.strip()


ALLOWED_CDT_CODES_V1 = {
    "D0120",
    "D0150",
    "D0274",
    "D0220",
    "D0230",
    "D1110",
    "D1120",
    "D2391",
    "D2392",
    "D2750",
}

APPROVED_PAYERS_V1 = {
    "Aetna",
    "UnitedHealthcare",
    "BCBS",
    "Cigna",
    "Delta Dental",
}

PROCEDURE_PAY_RATES_V1 = {
    "D0120": 0.96,
    "D0150": 0.94,
    "D0274": 0.93,
    "D0220": 0.92,
    "D0230": 0.91,
    "D1110": 0.96,
    "D1120": 0.95,
    "D2391": 0.92,
    "D2392": 0.91,
    "D2750": 0.88,
}


def _default_policy() -> UnderwritingPolicy:
    return UnderwritingPolicy(
        approved_payers=APPROVED_PAYERS_V1,
        excluded_plan_keywords={"medicaid", "capitation", "carve-out", "hmo"},
        allowed_procedures=ALLOWED_CDT_CODES_V1,
        procedure_pay_rate_threshold=0.90,
        min_practice_tenure_months=12,
        min_practice_clean_claim_rate=0.90,
        procedure_historical_pay_rate=PROCEDURE_PAY_RATES_V1,
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
def get_pool(pool_id: str) -> dict:
    with session_scope() as session:
        pool = session.exec(select(CapitalPool).where(CapitalPool.id == pool_id)).first()
        if pool is None:
            raise HTTPException(status_code=404, detail="Capital pool not found")
        return pool.model_dump()


@app.get("/health/capital")
def health_capital(pool_id: str = "POOL") -> dict:
    with session_scope() as session:
        pool = session.exec(select(CapitalPool).where(CapitalPool.id == pool_id)).first()
        if pool is None:
            return {
                "status": "error",
                "pool_id": pool_id,
                "message": "Capital pool not found",
                "invariants_ok": False,
            }

        issues: list[str] = []

        if pool.available_capital < 0:
            issues.append(f"available_capital is negative: {pool.available_capital}")
        if pool.capital_allocated < 0:
            issues.append(f"capital_allocated is negative: {pool.capital_allocated}")
        if pool.capital_pending_settlement < 0:
            issues.append(f"capital_pending_settlement is negative: {pool.capital_pending_settlement}")
        if pool.capital_returned < 0:
            issues.append(f"capital_returned is negative: {pool.capital_returned}")

        expected_available = pool.total_capital - pool.capital_allocated + pool.capital_returned
        if pool.available_capital != expected_available:
            issues.append(
                f"available_capital ({pool.available_capital}) != "
                f"total_capital ({pool.total_capital}) - capital_allocated ({pool.capital_allocated}) + "
                f"capital_returned ({pool.capital_returned}) = {expected_available}"
            )

        if pool.capital_pending_settlement > pool.capital_allocated:
            issues.append(
                f"capital_pending_settlement ({pool.capital_pending_settlement}) > "
                f"capital_allocated ({pool.capital_allocated})"
            )

        funded_claims = session.exec(
            select(Claim).where(Claim.status == ClaimStatus.funded)
        ).all()
        total_funded = sum(c.funded_amount for c in funded_claims)
        if total_funded != pool.capital_pending_settlement:
            issues.append(
                f"sum of funded claims ({total_funded}) != "
                f"capital_pending_settlement ({pool.capital_pending_settlement})"
            )

        practices = session.exec(select(Practice)).all()
        total_exposure = sum(p.current_exposure for p in practices)
        if total_exposure != pool.capital_allocated:
            issues.append(
                f"sum of practice exposures ({total_exposure}) != "
                f"capital_allocated ({pool.capital_allocated})"
            )

        invariants_ok = len(issues) == 0
        utilization_pct = (
            (pool.capital_allocated / pool.total_capital * 100)
            if pool.total_capital > 0 else 0.0
        )

        return {
            "status": "healthy" if invariants_ok else "unhealthy",
            "pool_id": pool_id,
            "invariants_ok": invariants_ok,
            "issues": issues if issues else None,
            "metrics": {
                "total_capital": pool.total_capital,
                "available_capital": pool.available_capital,
                "capital_allocated": pool.capital_allocated,
                "capital_pending_settlement": pool.capital_pending_settlement,
                "capital_returned": pool.capital_returned,
                "utilization_pct": round(utilization_pct, 2),
                "num_funded_claims": len(funded_claims),
                "num_settled_claims": pool.num_settled_claims,
                "avg_days_outstanding": (
                    round(pool.total_days_outstanding / pool.num_settled_claims, 1)
                    if pool.num_settled_claims > 0 else None
                ),
            },
        }


@app.get("/claims")
def list_claims(practice_id: Optional[str] = None) -> list[dict]:
    with session_scope() as session:
        stmt = select(Claim)
        if practice_id is not None:
            stmt = stmt.where(Claim.practice_id == practice_id)
        claims = session.exec(stmt).all()
        return [c.model_dump() for c in claims]


@app.get("/claims/{claim_id}/transitions")
def get_claim_transitions(claim_id: str) -> dict:
    with session_scope() as session:
        claim = session.exec(select(Claim).where(Claim.claim_id == claim_id)).first()
        if claim is None:
            raise HTTPException(status_code=404, detail="Claim not found")

        valid_transitions = get_valid_transitions(claim.status)
        return {
            "claim_id": claim.claim_id,
            "current_status": claim.status.value,
            "valid_transitions": [s.value for s in valid_transitions],
        }


@app.get("/practices")
def list_practices() -> list[dict]:
    with session_scope() as session:
        practices = session.exec(select(Practice)).all()
        return [p.model_dump() for p in practices]


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


@app.post("/claims/submit")
def submit_claim(req: ClaimSubmitRequest) -> dict:
    if req.practice_npi is None and req.practice_id is None:
        raise HTTPException(
            status_code=400,
            detail="Either practice_npi or practice_id must be provided"
        )

    logger.info(
        "Submitting claim: external_claim_id=%s, practice_npi=%s, practice_id=%s, payer=%s",
        req.external_claim_id, req.practice_npi, req.practice_id, req.payer
    )

    with session_scope() as session:
        practice: Optional[Practice] = None

        if req.practice_npi is not None:
            practice = session.exec(
                select(Practice).where(Practice.npi == req.practice_npi)
            ).first()
            if practice is None:
                logger.warning("Practice not found: npi=%s", req.practice_npi)
                raise HTTPException(
                    status_code=404,
                    detail=f"Practice not found with NPI: {req.practice_npi}"
                )

            if req.practice_id is not None and practice.id != req.practice_id:
                logger.warning(
                    "NPI/practice_id mismatch: npi=%s resolves to %s, but practice_id=%s provided",
                    req.practice_npi, practice.id, req.practice_id
                )
                raise HTTPException(
                    status_code=400,
                    detail=f"NPI {req.practice_npi} does not match practice_id {req.practice_id}"
                )
        else:
            practice = session.exec(
                select(Practice).where(Practice.id == req.practice_id)
            ).first()
            if practice is None:
                logger.warning("Practice not found: practice_id=%s", req.practice_id)
                raise HTTPException(
                    status_code=404,
                    detail=f"Practice not found: {req.practice_id}"
                )

        existing = session.exec(
            select(Claim).where(Claim.external_claim_id == req.external_claim_id)
        ).first()
        if existing is not None:
            logger.warning(
                "Duplicate external_claim_id: %s (existing claim_id=%s)",
                req.external_claim_id, existing.claim_id
            )
            raise HTTPException(
                status_code=400,
                detail=f"Claim with external_claim_id '{req.external_claim_id}' already exists"
            )

        claim_id = f"CLM-{uuid.uuid4().hex[:8].upper()}"

        raw_submission = json.dumps({
            "practice_npi": req.practice_npi,
            "practice_id": req.practice_id,
            "payer": req.payer,
            "procedure_codes": req.procedure_codes,
            "billed_amount": req.billed_amount,
            "expected_allowed_amount": req.expected_allowed_amount,
            "service_date": req.service_date.isoformat(),
            "external_claim_id": req.external_claim_id,
        })

        claim = Claim(
            claim_id=claim_id,
            practice_id=practice.id,
            payer=req.payer,
            procedure_code=";".join(req.procedure_codes),
            billed_amount=int(req.billed_amount * 100),
            expected_allowed_amount=int(req.expected_allowed_amount * 100),
            submission_date=date.today(),
            service_date=req.service_date,
            external_claim_id=req.external_claim_id,
            raw_submission=raw_submission,
            status=ClaimStatus.submitted,
        )
        session.add(claim)
        session.flush()

        logger.info(
            "Claim submitted successfully: claim_id=%s, external_claim_id=%s, practice_id=%s",
            claim_id, req.external_claim_id, practice.id
        )

        return {
            "claim_id": claim.claim_id,
            "practice_id": practice.id,
            "practice_npi": practice.npi,
            "external_claim_id": claim.external_claim_id,
            "status": claim.status.value,
            "message": "Claim submitted successfully",
        }


@app.post("/webhooks/clearinghouse")
def clearinghouse_webhook(req: ClearinghouseWebhookRequest) -> dict:
    logger.info(
        "Clearinghouse webhook received: external_claim_id=%s, status=%s",
        req.external_claim_id, req.status
    )

    with session_scope() as session:
        claim = session.exec(
            select(Claim).where(Claim.external_claim_id == req.external_claim_id)
        ).first()
        if claim is None:
            logger.warning("Claim not found for external_claim_id: %s", req.external_claim_id)
            raise HTTPException(
                status_code=404,
                detail=f"No claim found with external_claim_id: {req.external_claim_id}"
            )

        if claim.status != ClaimStatus.submitted:
            logger.warning(
                "Claim not in submitted status: claim_id=%s, status=%s",
                claim.claim_id, claim.status.value
            )
            raise HTTPException(
                status_code=400,
                detail=f"Claim {claim.claim_id} is not in 'submitted' status (current: {claim.status.value})"
            )

        if req.reason_codes:
            claim.reason_codes = ";".join(req.reason_codes)

        if req.status == "approved":
            claim.adjudication_status = AdjudicationStatus.approved
            claim.status = ClaimStatus.adjudicated
            if req.approved_amount is not None:
                claim.approved_amount = int(req.approved_amount * 100)
            logger.info(
                "Claim adjudicated as approved: claim_id=%s, approved_amount=%s",
                claim.claim_id, req.approved_amount
            )
        else:
            claim.adjudication_status = AdjudicationStatus.denied
            claim.status = ClaimStatus.exception
            logger.info(
                "Claim adjudicated as denied: claim_id=%s, reason_codes=%s",
                claim.claim_id, req.reason_codes
            )

        session.add(claim)
        session.flush()

        return {
            "claim_id": claim.claim_id,
            "external_claim_id": claim.external_claim_id,
            "status": claim.status.value,
            "adjudication_status": claim.adjudication_status.value,
            "message": f"Claim adjudicated as {req.status}",
        }


@app.post("/claims/{claim_id}/underwrite")
def underwrite(claim_id: str, req: UnderwriteRequest) -> dict:
    logger.info("Underwriting claim: claim_id=%s, pool_id=%s", claim_id, req.pool_id)

    with session_scope() as session:
        claim = session.exec(select(Claim).where(Claim.claim_id == claim_id)).first()
        if claim is None:
            logger.warning("Claim not found: claim_id=%s", claim_id)
            raise HTTPException(status_code=404, detail="Claim not found")

        try:
            validate_status_transition(claim.status, ClaimStatus.underwriting)
        except InvalidStatusTransitionError as e:
            logger.warning(
                "Invalid status transition for underwrite: claim_id=%s, current_status=%s",
                claim_id, claim.status.value
            )
            raise HTTPException(status_code=400, detail=e.message)

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
            claim.status = ClaimStatus.exception
            session.add(claim)
            logger.info(
                "Claim declined: claim_id=%s, reason_code=%s",
                claim_id, decision.reason_code
            )
        else:
            claim.status = ClaimStatus.underwriting
            session.add(claim)
            logger.info(
                "Claim approved for underwriting: claim_id=%s, funded_amount=%d",
                claim_id, decision.funded_amount
            )

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

        try:
            fund_claim_atomic(
                session=session,
                pool_id=req.pool_id,
                claim_id=claim_id,
                funded_amount=decision.funded_amount,
            )
        except LedgerError as e:
            raise HTTPException(status_code=400, detail=str(e))

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
                    id="Bright Smile Dental",
                    npi="1234567890",
                    tenure_months=36,
                    historical_clean_claim_rate=0.97,
                    payer_mix="Aetna:0.35;BCBS:0.40;Cigna:0.25",
                    max_exposure_limit=75_000,
                    current_exposure=0,
                )
            )
            session.add(
                Practice(
                    id="Downtown Family Dentistry",
                    npi="2345678901",
                    tenure_months=24,
                    historical_clean_claim_rate=0.95,
                    payer_mix="UnitedHealthcare:0.50;BCBS:0.30;Aetna:0.20",
                    max_exposure_limit=100_000,
                    current_exposure=0,
                )
            )
            session.add(
                Practice(
                    id="Coastal Orthodontics",
                    npi="3456789012",
                    tenure_months=18,
                    historical_clean_claim_rate=0.94,
                    payer_mix="Cigna:0.45;Aetna:0.35;BCBS:0.20",
                    max_exposure_limit=120_000,
                    current_exposure=0,
                )
            )

        claims = session.exec(select(Claim)).all()
        if req.seed_if_empty and len(claims) == 0:
            today = date.today()
            session.add(
                Claim(
                    claim_id="CLM-D001",
                    practice_id="Bright Smile Dental",
                    payer="Aetna",
                    procedure_code="D0120",
                    billed_amount=8_500,
                    expected_allowed_amount=6_800,
                    submission_date=today,
                )
            )
            session.add(
                Claim(
                    claim_id="CLM-D002",
                    practice_id="Downtown Family Dentistry",
                    payer="Delta Dental",
                    procedure_code="D1110",
                    billed_amount=12_500,
                    expected_allowed_amount=10_000,
                    submission_date=today,
                )
            )
            session.add(
                Claim(
                    claim_id="CLM-D003",
                    practice_id="Coastal Orthodontics",
                    payer="Cigna",
                    procedure_code="D2391",
                    billed_amount=22_500,
                    expected_allowed_amount=18_000,
                    submission_date=today,
                )
            )
            session.add(
                Claim(
                    claim_id="CLM-D004",
                    practice_id="Bright Smile Dental",
                    payer="BCBS",
                    procedure_code="D0274",
                    billed_amount=7_500,
                    expected_allowed_amount=6_000,
                    submission_date=today,
                )
            )
            session.add(
                Claim(
                    claim_id="CLM-D005",
                    practice_id="Downtown Family Dentistry",
                    payer="UnitedHealthcare",
                    procedure_code="D2750",
                    billed_amount=150_000,
                    expected_allowed_amount=120_000,
                    submission_date=today,
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

        try:
            settle_claim_atomic(
                session=session,
                pool_id=req.pool_id,
                claim_id=claim_id,
                settlement_date=req.settlement_date,
                settlement_amount=req.settlement_amount,
            )
        except LedgerError as e:
            raise HTTPException(status_code=400, detail=str(e))

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


@app.post("/reset")
def reset_demo(req: ResetDemoRequest) -> dict:
    """Reset demo to a clean, deterministic state.
    
    Clears all claims, practices, and capital pool, then seeds
    the same demo data every time for consistent investor demos.
    """
    with session_scope() as session:
        # Clear all existing data
        session.exec(select(Claim)).all()
        for claim in session.exec(select(Claim)).all():
            session.delete(claim)
        for practice in session.exec(select(Practice)).all():
            session.delete(practice)
        for pool in session.exec(select(CapitalPool)).all():
            session.delete(pool)
        session.flush()

    # Seed deterministic demo data (dental-focused for Spoonbill)
    with session_scope() as session:
        # Create capital pool with $1M starting capital
        pool = CapitalPool(
            id=req.pool_id,
            total_capital=1_000_000,
            available_capital=1_000_000,
            capital_allocated=0,
            capital_pending_settlement=0,
            capital_returned=0,
        )
        session.add(pool)

        # Create dental practices with realistic profiles
        # NPIs are 10-digit numbers; using realistic-looking demo NPIs
        session.add(
            Practice(
                id="Bright Smile Dental",
                npi="1234567890",
                tenure_months=36,
                historical_clean_claim_rate=0.97,
                payer_mix="Aetna:0.35;BCBS:0.40;Cigna:0.25",
                max_exposure_limit=75_000,
                current_exposure=0,
            )
        )
        session.add(
            Practice(
                id="Downtown Family Dentistry",
                npi="2345678901",
                tenure_months=24,
                historical_clean_claim_rate=0.95,
                payer_mix="UnitedHealthcare:0.50;BCBS:0.30;Aetna:0.20",
                max_exposure_limit=100_000,
                current_exposure=0,
            )
        )
        session.add(
            Practice(
                id="Coastal Orthodontics",
                npi="3456789012",
                tenure_months=18,
                historical_clean_claim_rate=0.94,
                payer_mix="Cigna:0.45;Aetna:0.35;BCBS:0.20",
                max_exposure_limit=120_000,
                current_exposure=0,
            )
        )

        today = date.today()

        session.add(
            Claim(
                claim_id="CLM-D001",
                practice_id="Bright Smile Dental",
                payer="Aetna",
                procedure_code="D0120",
                billed_amount=8_500,
                expected_allowed_amount=6_800,
                submission_date=today,
            )
        )
        session.add(
            Claim(
                claim_id="CLM-D002",
                practice_id="Downtown Family Dentistry",
                payer="Delta Dental",
                procedure_code="D1110",
                billed_amount=12_500,
                expected_allowed_amount=10_000,
                submission_date=today,
            )
        )
        session.add(
            Claim(
                claim_id="CLM-D003",
                practice_id="Coastal Orthodontics",
                payer="Cigna",
                procedure_code="D2391",
                billed_amount=22_500,
                expected_allowed_amount=18_000,
                submission_date=today,
            )
        )
        session.add(
            Claim(
                claim_id="CLM-D004",
                practice_id="Bright Smile Dental",
                payer="BCBS",
                procedure_code="D0274",
                billed_amount=7_500,
                expected_allowed_amount=6_000,
                submission_date=today,
            )
        )
        session.add(
            Claim(
                claim_id="CLM-D005",
                practice_id="Downtown Family Dentistry",
                payer="UnitedHealthcare",
                procedure_code="D2750",
                billed_amount=150_000,
                expected_allowed_amount=120_000,
                submission_date=today,
            )
        )

        session.flush()

    return get_state(pool_id=req.pool_id)

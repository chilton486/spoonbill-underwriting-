"""API endpoints for ontology objects and insights.

Provides practice-scoped CRUD and analytics endpoints for:
- Providers, Payers, PayerContracts, ProcedureCodes
- Practice summary, payer performance, provider productivity
- Procedure risk, claim cycle times, reconciliation, funding decisions
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.user import User
from ..services.ontology_crud import (
    ProviderService,
    PayerService,
    PayerContractService,
    ProcedureCodeService,
    OntologyInsightsService,
)
from .auth import require_practice_manager, require_spoonbill_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/practices", tags=["ontology-objects"])


def _check_practice(current_user: User, practice_id: int):
    if current_user.practice_id != practice_id:
        raise HTTPException(status_code=404, detail="Practice not found")


# ─── Provider endpoints ───


class CreateProviderRequest(BaseModel):
    full_name: str
    npi: Optional[str] = None
    specialty: Optional[str] = None
    role: str = "ASSOCIATE"


@router.get("/{practice_id}/providers")
def list_providers(
    practice_id: int,
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_practice_manager),
):
    _check_practice(current_user, practice_id)
    return ProviderService.list_providers(db, practice_id, active_only=active_only)


@router.get("/{practice_id}/providers/{provider_id}")
def get_provider(
    practice_id: int,
    provider_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_practice_manager),
):
    _check_practice(current_user, practice_id)
    provider = ProviderService.get_provider(db, provider_id, practice_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider


@router.post("/{practice_id}/providers")
def create_provider(
    practice_id: int,
    req: CreateProviderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_practice_manager),
):
    _check_practice(current_user, practice_id)
    provider = ProviderService.create_provider(
        db, practice_id,
        full_name=req.full_name,
        npi=req.npi,
        specialty=req.specialty,
        role=req.role,
    )
    db.commit()
    return {"id": provider.id, "full_name": provider.full_name, "status": "created"}


# ─── Payer endpoints ───


@router.get("/{practice_id}/payers")
def list_payers(
    practice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_practice_manager),
):
    _check_practice(current_user, practice_id)
    return PayerService.list_payers(db)


# ─── Payer Contract endpoints ───


@router.get("/{practice_id}/contracts")
def list_payer_contracts(
    practice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_practice_manager),
):
    _check_practice(current_user, practice_id)
    return PayerContractService.list_contracts(db, practice_id)


# ─── Procedure Code endpoints ───


@router.get("/{practice_id}/procedure-codes")
def list_procedure_codes(
    practice_id: int,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_practice_manager),
):
    _check_practice(current_user, practice_id)
    return ProcedureCodeService.list_procedure_codes(db, category=category)


# ─── Ontology Insight endpoints ───


@router.get("/{practice_id}/ontology/summary")
def get_practice_summary(
    practice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_practice_manager),
):
    """Practice ontology summary: profile, payer mix, capital, claim volume."""
    _check_practice(current_user, practice_id)
    try:
        return OntologyInsightsService.get_practice_summary(db, practice_id)
    except Exception as e:
        logger.error("practice summary failed for %s: %s", practice_id, e)
        raise HTTPException(status_code=503, detail="Ontology data unavailable")


@router.get("/{practice_id}/ontology/payer-performance")
def get_payer_performance(
    practice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_practice_manager),
):
    """Payer performance: denial rates, cycle times, reimbursement rates."""
    _check_practice(current_user, practice_id)
    try:
        return OntologyInsightsService.get_payer_performance(db, practice_id)
    except Exception as e:
        logger.error("payer performance failed for %s: %s", practice_id, e)
        raise HTTPException(status_code=503, detail="Ontology data unavailable")


@router.get("/{practice_id}/ontology/provider-productivity")
def get_provider_productivity(
    practice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_practice_manager),
):
    """Provider productivity: procedure mix, claim volume, reimbursement."""
    _check_practice(current_user, practice_id)
    try:
        return OntologyInsightsService.get_provider_productivity(db, practice_id)
    except Exception as e:
        logger.error("provider productivity failed for %s: %s", practice_id, e)
        raise HTTPException(status_code=503, detail="Ontology data unavailable")


@router.get("/{practice_id}/ontology/procedure-risk")
def get_procedure_risk(
    practice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_practice_manager),
):
    """Procedure risk summary: denial patterns, documentation requirements."""
    _check_practice(current_user, practice_id)
    try:
        return OntologyInsightsService.get_procedure_risk_summary(db, practice_id)
    except Exception as e:
        logger.error("procedure risk failed for %s: %s", practice_id, e)
        raise HTTPException(status_code=503, detail="Ontology data unavailable")


@router.get("/{practice_id}/ontology/cycle-times")
def get_claim_cycle_times(
    practice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_practice_manager),
):
    """Claim cycle time analytics: aging buckets, resolution times."""
    _check_practice(current_user, practice_id)
    try:
        return OntologyInsightsService.get_claim_cycle_times(db, practice_id)
    except Exception as e:
        logger.error("cycle times failed for %s: %s", practice_id, e)
        raise HTTPException(status_code=503, detail="Ontology data unavailable")


@router.get("/{practice_id}/ontology/reconciliation")
def get_reconciliation_summary(
    practice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_practice_manager),
):
    """Reconciliation summary: remittance match rates, unresolved issues."""
    _check_practice(current_user, practice_id)
    try:
        return OntologyInsightsService.get_reconciliation_summary(db, practice_id)
    except Exception as e:
        logger.error("reconciliation failed for %s: %s", practice_id, e)
        raise HTTPException(status_code=503, detail="Ontology data unavailable")


@router.get("/{practice_id}/ontology/funding-decisions")
def get_funding_decisions(
    practice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_practice_manager),
):
    """Funding decisions summary: approvals, denials, risk scores."""
    _check_practice(current_user, practice_id)
    try:
        return OntologyInsightsService.get_funding_decisions_summary(db, practice_id)
    except Exception as e:
        logger.error("funding decisions failed for %s: %s", practice_id, e)
        raise HTTPException(status_code=503, detail="Ontology data unavailable")

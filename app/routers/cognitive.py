"""Cognitive underwriting API endpoints.

Provides endpoints for:
- Viewing underwriting runs and cognitive decisions
- Triggering EOB parsing
- Triggering ontology update generation
- Checking cognitive underwriting status/config
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.claim import Claim
from ..models.practice import Practice
from ..models.underwriting_run import UnderwritingRun
from ..models.user import User
from ..schemas.cognitive import (
    ParseEobInput,
    ParseEobOutput,
    OntologyUpdateInput,
    OntologyUpdateOutput,
    UnderwritingRunResponse,
)
from ..services.cognitive_underwriting import CognitiveUnderwritingService
from ..services.anthropic_service import AnthropicService
from ..config import get_settings
from .auth import get_current_user, require_spoonbill_user

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/cognitive", tags=["cognitive-underwriting"])


# ── Status / Config ────────────────────────────────────────────────────

@router.get("/status")
def get_cognitive_status(
    current_user: User = Depends(require_spoonbill_user),
):
    """Check cognitive underwriting configuration and availability."""
    return {
        "anthropic_enabled": settings.anthropic_enabled,
        "anthropic_model": settings.anthropic_model,
        "anthropic_configured": bool(settings.anthropic_api_key),
        "cognitive_underwriting_enabled": settings.cognitive_underwriting_enabled,
        "cognitive_eob_parsing_enabled": settings.cognitive_eob_parsing_enabled,
        "cognitive_ontology_updates_enabled": settings.cognitive_ontology_updates_enabled,
        "prompt_version": settings.anthropic_prompt_version,
        "is_available": AnthropicService.is_available(),
    }


# ── Underwriting Runs ─────────────────────────────────────────────────

@router.get("/runs", response_model=List[UnderwritingRunResponse])
def list_underwriting_runs(
    claim_id: Optional[int] = Query(None),
    practice_id: Optional[int] = Query(None),
    run_type: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_user),
):
    """List underwriting runs with optional filtering."""
    query = db.query(UnderwritingRun)
    if claim_id:
        query = query.filter(UnderwritingRun.claim_id == claim_id)
    if practice_id:
        query = query.filter(UnderwritingRun.practice_id == practice_id)
    if run_type:
        query = query.filter(UnderwritingRun.run_type == run_type)
    query = query.order_by(UnderwritingRun.created_at.desc()).limit(limit)
    return query.all()


@router.get("/runs/{run_id}", response_model=UnderwritingRunResponse)
def get_underwriting_run(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_user),
):
    """Get a single underwriting run by ID."""
    run = db.query(UnderwritingRun).filter(UnderwritingRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Underwriting run not found")
    return run


@router.get("/claims/{claim_id}/runs", response_model=List[UnderwritingRunResponse])
def get_claim_underwriting_runs(
    claim_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_user),
):
    """Get all underwriting runs for a specific claim."""
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    runs = (
        db.query(UnderwritingRun)
        .filter(UnderwritingRun.claim_id == claim_id)
        .order_by(UnderwritingRun.created_at.desc())
        .all()
    )
    return runs


@router.get("/claims/{claim_id}/cognitive-summary")
def get_claim_cognitive_summary(
    claim_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_user),
):
    """Get a cognitive underwriting summary for a claim.

    Returns the latest cognitive run data formatted for UI display.
    """
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    latest_run = (
        db.query(UnderwritingRun)
        .filter(
            UnderwritingRun.claim_id == claim_id,
            UnderwritingRun.run_type == "underwrite_claim",
        )
        .order_by(UnderwritingRun.created_at.desc())
        .first()
    )

    if not latest_run:
        return {
            "has_cognitive_data": False,
            "cognitive_enabled": CognitiveUnderwritingService.is_cognitive_enabled(),
            "message": "No cognitive underwriting data available for this claim",
        }

    output = latest_run.output_json or {}

    return {
        "has_cognitive_data": True,
        "run_id": latest_run.id,
        "model_provider": latest_run.model_provider,
        "model_name": latest_run.model_name,
        "prompt_version": latest_run.prompt_version,
        "created_at": latest_run.created_at.isoformat() if latest_run.created_at else None,
        "latency_ms": latest_run.latency_ms,
        "fallback_used": latest_run.fallback_used,
        "fallback_reason": latest_run.fallback_reason,
        "parse_success": latest_run.parse_success,
        # Decision data
        "recommendation": latest_run.recommendation,
        "deterministic_recommendation": latest_run.deterministic_recommendation,
        "merged_recommendation": latest_run.merged_recommendation,
        "risk_score": latest_run.risk_score,
        "confidence_score": latest_run.confidence_score,
        # Structured output
        "suggested_advance_rate": output.get("suggested_advance_rate"),
        "suggested_max_advance_amount_cents": output.get("suggested_max_advance_amount_cents"),
        "fee_rate_suggestion": output.get("fee_rate_suggestion"),
        "required_documents": output.get("required_documents", []),
        "key_risk_factors": output.get("key_risk_factors", []),
        "rationale_summary": output.get("rationale_summary", ""),
        "rationale_detailed": output.get("rationale_detailed", ""),
        "policy_flags": output.get("policy_flags", []),
        "ontology_observations": output.get("ontology_observations", []),
        "next_actions": output.get("next_actions", []),
        # Review info
        "reviewer_override": latest_run.reviewer_override,
        "reviewer_notes": latest_run.reviewer_notes,
        "reviewed_at": latest_run.reviewed_at.isoformat() if latest_run.reviewed_at else None,
    }


# ── EOB Parsing ────────────────────────────────────────────────────────

@router.post("/parse-eob")
def parse_eob(
    input_data: ParseEobInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_user),
):
    """Parse EOB/ERA text into structured remittance data.

    Requires cognitive_eob_parsing_enabled=true and valid Anthropic config.
    """
    if not settings.cognitive_eob_parsing_enabled:
        raise HTTPException(
            status_code=400,
            detail="Cognitive EOB parsing is not enabled. Set COGNITIVE_EOB_PARSING_ENABLED=true",
        )
    if not AnthropicService.is_available():
        raise HTTPException(
            status_code=503,
            detail="Anthropic service is not available. Check ANTHROPIC_ENABLED and ANTHROPIC_API_KEY",
        )

    practice_id = input_data.practice_id or 0
    output, run = CognitiveUnderwritingService.run_eob_parsing(
        db, input_data, practice_id=practice_id,
    )
    db.commit()

    if output is None:
        error_msg = "EOB parsing failed"
        if run and run.fallback_reason:
            error_msg += f": {run.fallback_reason}"
        raise HTTPException(status_code=500, detail=error_msg)

    return {
        "success": True,
        "run_id": run.id if run else None,
        "result": output.model_dump(),
    }


# ── Ontology Updates ───────────────────────────────────────────────────

@router.post("/ontology-updates")
def generate_ontology_updates(
    input_data: OntologyUpdateInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_user),
):
    """Generate ontology update proposals from claim/remittance context.

    Requires cognitive_ontology_updates_enabled=true and valid Anthropic config.
    Returns proposed updates that should be reviewed before applying.
    """
    if not settings.cognitive_ontology_updates_enabled:
        raise HTTPException(
            status_code=400,
            detail="Cognitive ontology updates are not enabled. Set COGNITIVE_ONTOLOGY_UPDATES_ENABLED=true",
        )
    if not AnthropicService.is_available():
        raise HTTPException(
            status_code=503,
            detail="Anthropic service is not available. Check ANTHROPIC_ENABLED and ANTHROPIC_API_KEY",
        )

    # Verify practice exists
    practice = db.query(Practice).filter(Practice.id == input_data.practice_id).first()
    if not practice:
        raise HTTPException(status_code=404, detail="Practice not found")

    output, run = CognitiveUnderwritingService.run_ontology_updates(
        db, input_data, claim_id=input_data.claim_id,
    )
    db.commit()

    if output is None:
        error_msg = "Ontology update generation failed"
        if run and run.fallback_reason:
            error_msg += f": {run.fallback_reason}"
        raise HTTPException(status_code=500, detail=error_msg)

    return {
        "success": True,
        "run_id": run.id if run else None,
        "review_needed": output.review_needed,
        "result": output.model_dump(),
    }


# ── Practice-scoped Cognitive Insights ─────────────────────────────────

@router.get("/practices/{practice_id}/cognitive-overview")
def get_practice_cognitive_overview(
    practice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_user),
):
    """Get cognitive underwriting overview for a practice.

    Shows aggregate stats on cognitive runs, model performance, etc.
    """
    practice = db.query(Practice).filter(Practice.id == practice_id).first()
    if not practice:
        raise HTTPException(status_code=404, detail="Practice not found")

    # Get run stats
    from sqlalchemy import func
    total_runs = (
        db.query(func.count(UnderwritingRun.id))
        .filter(UnderwritingRun.practice_id == practice_id)
        .scalar()
    ) or 0

    successful_runs = (
        db.query(func.count(UnderwritingRun.id))
        .filter(
            UnderwritingRun.practice_id == practice_id,
            UnderwritingRun.parse_success == True,
            UnderwritingRun.fallback_used == False,
        )
        .scalar()
    ) or 0

    fallback_runs = (
        db.query(func.count(UnderwritingRun.id))
        .filter(
            UnderwritingRun.practice_id == practice_id,
            UnderwritingRun.fallback_used == True,
        )
        .scalar()
    ) or 0

    avg_latency = (
        db.query(func.avg(UnderwritingRun.latency_ms))
        .filter(
            UnderwritingRun.practice_id == practice_id,
            UnderwritingRun.latency_ms.isnot(None),
        )
        .scalar()
    )

    avg_risk = (
        db.query(func.avg(UnderwritingRun.risk_score))
        .filter(
            UnderwritingRun.practice_id == practice_id,
            UnderwritingRun.risk_score.isnot(None),
        )
        .scalar()
    )

    avg_confidence = (
        db.query(func.avg(UnderwritingRun.confidence_score))
        .filter(
            UnderwritingRun.practice_id == practice_id,
            UnderwritingRun.confidence_score.isnot(None),
        )
        .scalar()
    )

    # Run type distribution
    run_types = (
        db.query(UnderwritingRun.run_type, func.count(UnderwritingRun.id))
        .filter(UnderwritingRun.practice_id == practice_id)
        .group_by(UnderwritingRun.run_type)
        .all()
    )

    # Recommendation distribution
    recommendations = (
        db.query(UnderwritingRun.merged_recommendation, func.count(UnderwritingRun.id))
        .filter(
            UnderwritingRun.practice_id == practice_id,
            UnderwritingRun.merged_recommendation.isnot(None),
        )
        .group_by(UnderwritingRun.merged_recommendation)
        .all()
    )

    return {
        "practice_id": practice_id,
        "practice_name": practice.name,
        "cognitive_enabled": CognitiveUnderwritingService.is_cognitive_enabled(),
        "total_runs": total_runs,
        "successful_runs": successful_runs,
        "fallback_runs": fallback_runs,
        "success_rate": round(successful_runs / total_runs, 3) if total_runs > 0 else None,
        "avg_latency_ms": round(avg_latency) if avg_latency else None,
        "avg_risk_score": round(avg_risk, 3) if avg_risk else None,
        "avg_confidence_score": round(avg_confidence, 3) if avg_confidence else None,
        "run_type_distribution": {rt: count for rt, count in run_types},
        "recommendation_distribution": {rec: count for rec, count in recommendations},
    }

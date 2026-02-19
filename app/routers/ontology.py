import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.user import User
from ..models.practice import Practice
from ..services.ontology_v2 import OntologyBuilderV2
from ..services.ontology_brief import generate_brief_from_context
from ..services.audit import AuditService
from .auth import require_practice_manager, require_spoonbill_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/practices", tags=["ontology"])


def _check_practice(current_user, practice_id):
    if current_user.practice_id != practice_id:
        raise HTTPException(status_code=404, detail="Practice not found")


@router.get("/{practice_id}/ontology/context")
def get_ontology_context(
    practice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_practice_manager),
):
    _check_practice(current_user, practice_id)

    try:
        OntologyBuilderV2.build_practice_ontology(db, practice_id, actor_user_id=current_user.id)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("ontology build failed for practice %s: %s", practice_id, e)
        raise HTTPException(status_code=503, detail="Ontology data unavailable — migration may be pending; see /diag")

    try:
        context = OntologyBuilderV2.get_practice_context(db, practice_id)
        return context
    except Exception as e:
        logger.error("ontology context read failed for practice %s: %s", practice_id, e)
        raise HTTPException(status_code=503, detail="Ontology data unavailable — migration may be pending; see /diag")


@router.post("/{practice_id}/ontology/rebuild")
def rebuild_ontology(
    practice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_practice_manager),
):
    _check_practice(current_user, practice_id)

    result = OntologyBuilderV2.build_practice_ontology(db, practice_id, actor_user_id=current_user.id)
    db.commit()
    return {"status": "rebuilt", "objects": result["objects"], "metrics": result["metrics"]}


@router.post("/{practice_id}/ontology/brief")
def generate_ontology_brief(
    practice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_practice_manager),
):
    _check_practice(current_user, practice_id)

    context = OntologyBuilderV2.get_practice_context(db, practice_id)
    brief = generate_brief_from_context(context)

    AuditService.log_event(
        db, claim_id=None, action="ontology_brief_generated",
        actor_user_id=current_user.id,
        metadata={"practice_id": practice_id, "version": "v2", "has_risks": len(brief.get("risks", [])) > 0},
    )
    db.commit()

    return brief


@router.get("/{practice_id}/ontology/cohorts")
def get_ontology_cohorts(
    practice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_practice_manager),
):
    _check_practice(current_user, practice_id)
    try:
        return OntologyBuilderV2.get_cohorts(db, practice_id)
    except Exception as e:
        logger.error("ontology cohorts failed for practice %s: %s", practice_id, e)
        raise HTTPException(status_code=503, detail="Ontology data unavailable — migration may be pending; see /diag")


@router.get("/{practice_id}/ontology/cfo")
def get_cfo_360(
    practice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_practice_manager),
):
    _check_practice(current_user, practice_id)
    try:
        return OntologyBuilderV2.get_cfo_360(db, practice_id)
    except Exception as e:
        logger.error("ontology cfo failed for practice %s: %s", practice_id, e)
        raise HTTPException(status_code=503, detail="Ontology data unavailable — migration may be pending; see /diag")


@router.get("/{practice_id}/ontology/risks")
def get_ontology_risks(
    practice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_practice_manager),
):
    _check_practice(current_user, practice_id)
    try:
        return OntologyBuilderV2.get_risks(db, practice_id)
    except Exception as e:
        logger.error("ontology risks failed for practice %s: %s", practice_id, e)
        raise HTTPException(status_code=503, detail="Ontology data unavailable — migration may be pending; see /diag")


@router.get("/{practice_id}/ontology/graph")
def get_ontology_graph(
    practice_id: int,
    mode: str = "revenue_cycle",
    range: str = "90d",
    payer: Optional[str] = None,
    state: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 150,
    focus_node_id: Optional[str] = None,
    hops: int = 2,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_practice_manager),
):
    _check_practice(current_user, practice_id)
    try:
        return OntologyBuilderV2.get_graph(
            db, practice_id,
            mode=mode, range_key=range, payer_filter=payer,
            state_filter=state, limit=limit,
            focus_node_id=focus_node_id, hops=hops, search=search,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("ontology graph failed for practice %s: %s", practice_id, e)
        raise HTTPException(status_code=503, detail="Ontology data unavailable — migration may be pending; see /diag")


@router.get("/{practice_id}/ontology/retention")
def get_patient_retention(
    practice_id: int,
    range: str = "90d",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_practice_manager),
):
    _check_practice(current_user, practice_id)
    try:
        return OntologyBuilderV2.get_patient_retention(db, practice_id, range_key=range)
    except Exception as e:
        logger.error("ontology retention failed for practice %s: %s", practice_id, e)
        raise HTTPException(status_code=503, detail="Ontology data unavailable — migration may be pending; see /diag")


@router.get("/{practice_id}/ontology/reimbursement")
def get_reimbursement_metrics(
    practice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_practice_manager),
):
    _check_practice(current_user, practice_id)
    try:
        return OntologyBuilderV2.get_reimbursement_metrics(db, practice_id)
    except Exception as e:
        logger.error("ontology reimbursement failed for practice %s: %s", practice_id, e)
        raise HTTPException(status_code=503, detail="Ontology data unavailable — migration may be pending; see /diag")


@router.get("/{practice_id}/ontology/rcm")
def get_rcm_ops(
    practice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_practice_manager),
):
    _check_practice(current_user, practice_id)
    try:
        return OntologyBuilderV2.get_rcm_ops(db, practice_id)
    except Exception as e:
        logger.error("ontology rcm failed for practice %s: %s", practice_id, e)
        raise HTTPException(status_code=503, detail="Ontology data unavailable — migration may be pending; see /diag")


class AdjustLimitRequest(BaseModel):
    new_limit: int
    reason: str


@router.post("/{practice_id}/limit")
def adjust_practice_limit(
    practice_id: int,
    req: AdjustLimitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_practice_manager),
):
    _check_practice(current_user, practice_id)

    practice = db.query(Practice).filter(Practice.id == practice_id).first()
    if not practice:
        raise HTTPException(status_code=404, detail="Practice not found")

    old_limit = practice.funding_limit_cents
    practice.funding_limit_cents = req.new_limit

    AuditService.log_event(
        db, claim_id=None, action="limit_adjusted",
        actor_user_id=current_user.id,
        metadata={
            "practice_id": practice_id,
            "old_limit_cents": old_limit,
            "new_limit_cents": req.new_limit,
            "reason": req.reason,
        },
    )
    db.commit()

    return {
        "practice_id": practice_id,
        "old_limit_cents": old_limit,
        "new_limit_cents": req.new_limit,
    }

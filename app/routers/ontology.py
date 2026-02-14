from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.user import User
from ..models.practice import Practice
from ..services.ontology import OntologyBuilder
from ..services.ontology_brief import generate_brief_from_context
from ..services.audit import AuditService
from .auth import require_practice_manager, require_spoonbill_user

router = APIRouter(prefix="/practices", tags=["ontology"])


@router.get("/{practice_id}/ontology/context")
def get_ontology_context(
    practice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_practice_manager),
):
    if current_user.practice_id != practice_id:
        raise HTTPException(status_code=404, detail="Practice not found")

    OntologyBuilder.build_practice_ontology(db, practice_id, actor_user_id=current_user.id)
    db.commit()

    context = OntologyBuilder.get_practice_context(db, practice_id)
    return context


@router.post("/{practice_id}/ontology/rebuild")
def rebuild_ontology(
    practice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_practice_manager),
):
    if current_user.practice_id != practice_id:
        raise HTTPException(status_code=404, detail="Practice not found")

    result = OntologyBuilder.build_practice_ontology(db, practice_id, actor_user_id=current_user.id)
    db.commit()
    return {"status": "rebuilt", "objects": result["objects"], "metrics": result["metrics"]}


@router.post("/{practice_id}/ontology/brief")
def generate_ontology_brief(
    practice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_practice_manager),
):
    if current_user.practice_id != practice_id:
        raise HTTPException(status_code=404, detail="Practice not found")

    context = OntologyBuilder.get_practice_context(db, practice_id)
    brief = generate_brief_from_context(context)

    AuditService.log_event(
        db, claim_id=None, action="ontology_brief_generated",
        actor_user_id=current_user.id,
        metadata={"practice_id": practice_id, "has_risks": len(brief.get("risks", [])) > 0},
    )
    db.commit()

    return brief


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
    if current_user.practice_id != practice_id:
        raise HTTPException(status_code=404, detail="Practice not found")

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

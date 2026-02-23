import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from ..models.ops import OpsTask, TaskStatus, PlaybookType
from ..models.claim import Claim, ClaimStatus
from ..models.payment import PaymentIntent, PaymentIntentStatus
from ..models.integration import IntegrationSyncRun, SyncRunStatus
from ..services.audit import AuditService

logger = logging.getLogger(__name__)

PLAYBOOK_TEMPLATES = {
    PlaybookType.PAYMENT_FAILED.value: {
        "title_template": "Resolve failed payment for claim #{claim_id}",
        "description": "Payment failed. Review failure reason, contact practice if needed, retry or escalate.",
        "priority": "high",
        "sla_hours": 24,
    },
    PlaybookType.INTEGRATION_SYNC_FAILED.value: {
        "title_template": "Fix integration sync failure for practice #{practice_id}",
        "description": "Integration sync run failed. Check connector logs, verify credentials, re-run sync.",
        "priority": "high",
        "sla_hours": 8,
    },
    PlaybookType.CLAIM_MISSING_INFO.value: {
        "title_template": "Complete missing info for claim #{claim_id}",
        "description": "Claim is missing required information. Contact practice to gather missing fields.",
        "priority": "medium",
        "sla_hours": 48,
    },
    PlaybookType.DENIAL_SPIKE.value: {
        "title_template": "Investigate denial spike for practice #{practice_id}",
        "description": "Elevated denial rate detected. Analyze payer patterns, review recent claims, flag for ops review.",
        "priority": "high",
        "sla_hours": 12,
    },
}


class PlaybookService:
    @staticmethod
    def run_playbook(
        db: Session,
        playbook_type: str,
        practice_id: Optional[int] = None,
        claim_id: Optional[int] = None,
        payment_intent_id: Optional[str] = None,
        actor_user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        template = PLAYBOOK_TEMPLATES.get(playbook_type)
        if not template:
            return {"success": False, "error": f"Unknown playbook type: {playbook_type}"}

        title = template["title_template"].format(
            claim_id=claim_id or "?",
            practice_id=practice_id or "?",
        )

        import uuid as uuid_mod
        pi_id = uuid_mod.UUID(payment_intent_id) if payment_intent_id else None

        sla_hours = template["sla_hours"]
        due_at = datetime.utcnow() + timedelta(hours=sla_hours)

        task = OpsTask(
            title=title,
            description=template["description"],
            status=TaskStatus.OPEN.value,
            priority=template["priority"],
            playbook_type=playbook_type,
            practice_id=practice_id,
            claim_id=claim_id,
            payment_intent_id=pi_id,
            due_at=due_at,
        )
        db.add(task)
        db.flush()

        AuditService.log_event(
            db=db,
            claim_id=claim_id,
            action="PLAYBOOK_RUN",
            actor_user_id=actor_user_id,
            metadata={
                "playbook_type": playbook_type,
                "task_id": task.id,
                "practice_id": practice_id,
                "sla_hours": sla_hours,
            },
        )
        db.commit()

        return {
            "success": True,
            "task": {
                "id": task.id,
                "title": task.title,
                "status": task.status,
                "priority": task.priority,
                "playbook_type": task.playbook_type,
                "due_at": task.due_at.isoformat() if task.due_at else None,
            },
        }

    @staticmethod
    def get_tasks(
        db: Session,
        status_filter: Optional[str] = None,
        practice_id: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        q = db.query(OpsTask)
        if status_filter:
            q = q.filter(OpsTask.status == status_filter)
        if practice_id:
            q = q.filter(OpsTask.practice_id == practice_id)

        total = q.count()
        tasks = q.order_by(desc(OpsTask.created_at)).offset(offset).limit(limit).all()

        now = datetime.utcnow()
        items = []
        for t in tasks:
            overdue = False
            sla_remaining_seconds = None
            if t.due_at and t.status in (TaskStatus.OPEN.value, TaskStatus.IN_PROGRESS.value):
                delta = (t.due_at - now).total_seconds()
                sla_remaining_seconds = max(0, int(delta))
                overdue = delta < 0

            items.append({
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "status": t.status,
                "priority": t.priority,
                "playbook_type": t.playbook_type,
                "practice_id": t.practice_id,
                "claim_id": t.claim_id,
                "payment_intent_id": str(t.payment_intent_id) if t.payment_intent_id else None,
                "owner_user_id": t.owner_user_id,
                "due_at": t.due_at.isoformat() if t.due_at else None,
                "overdue": overdue,
                "sla_remaining_seconds": sla_remaining_seconds,
                "resolved_at": t.resolved_at.isoformat() if t.resolved_at else None,
                "resolution_note": t.resolution_note,
                "created_at": t.created_at.isoformat(),
                "updated_at": t.updated_at.isoformat(),
            })

        status_counts = dict(
            db.query(OpsTask.status, func.count(OpsTask.id))
            .group_by(OpsTask.status).all()
        )

        return {
            "items": items,
            "total": total,
            "status_counts": {
                "OPEN": status_counts.get(TaskStatus.OPEN.value, 0),
                "IN_PROGRESS": status_counts.get(TaskStatus.IN_PROGRESS.value, 0),
                "RESOLVED": status_counts.get(TaskStatus.RESOLVED.value, 0),
                "CANCELLED": status_counts.get(TaskStatus.CANCELLED.value, 0),
            },
        }

    @staticmethod
    def update_task(
        db: Session,
        task_id: int,
        status: Optional[str] = None,
        owner_user_id: Optional[int] = None,
        resolution_note: Optional[str] = None,
        actor_user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        task = db.query(OpsTask).filter(OpsTask.id == task_id).first()
        if not task:
            return {"success": False, "error": "Task not found"}

        old_status = task.status
        if status:
            task.status = status
            if status in (TaskStatus.RESOLVED.value, TaskStatus.CANCELLED.value):
                task.resolved_at = datetime.utcnow()
        if owner_user_id is not None:
            task.owner_user_id = owner_user_id
        if resolution_note is not None:
            task.resolution_note = resolution_note

        AuditService.log_event(
            db=db,
            claim_id=task.claim_id,
            action="TASK_UPDATED",
            actor_user_id=actor_user_id,
            metadata={
                "task_id": task_id,
                "old_status": old_status,
                "new_status": task.status,
                "resolution_note": resolution_note,
            },
        )
        db.commit()

        return {
            "success": True,
            "task": {
                "id": task.id,
                "title": task.title,
                "status": task.status,
                "priority": task.priority,
                "owner_user_id": task.owner_user_id,
                "resolved_at": task.resolved_at.isoformat() if task.resolved_at else None,
            },
        }

import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.user import User
from ..models.integration import (
    IntegrationConnection,
    IntegrationSyncRun,
    IntegrationProvider,
    IntegrationStatus,
    SyncRunStatus,
)
from ..schemas.integration import (
    IntegrationStatusResponse,
    IntegrationSyncRunResponse,
    CSVUploadResponse,
    IngestionSummary,
)
from ..integrations.csv_parser import parse_claims_csv, parse_lines_csv, build_external_claims
from ..integrations.open_dental.provider import OpenDentalProvider, OpenDentalNotConfigured
from ..services.ingestion import ingest_external_claims
from .auth import require_practice_manager, require_spoonbill_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/practice/integrations", tags=["integrations"])


def _get_or_create_connection(db: Session, practice_id: int) -> IntegrationConnection:
    conn = db.query(IntegrationConnection).filter(
        IntegrationConnection.practice_id == practice_id,
        IntegrationConnection.provider == IntegrationProvider.OPEN_DENTAL.value,
    ).first()
    if not conn:
        conn = IntegrationConnection(
            practice_id=practice_id,
            provider=IntegrationProvider.OPEN_DENTAL.value,
            status=IntegrationStatus.INACTIVE.value,
        )
        db.add(conn)
        db.flush()
    return conn


@router.get("/open-dental/status", response_model=IntegrationStatusResponse)
def get_integration_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_practice_manager),
):
    practice_id = current_user.practice_id
    conn = db.query(IntegrationConnection).filter(
        IntegrationConnection.practice_id == practice_id,
        IntegrationConnection.provider == IntegrationProvider.OPEN_DENTAL.value,
    ).first()

    if not conn:
        return IntegrationStatusResponse(connected=False)

    recent_runs = (
        db.query(IntegrationSyncRun)
        .filter(IntegrationSyncRun.connection_id == conn.id)
        .order_by(IntegrationSyncRun.started_at.desc())
        .limit(10)
        .all()
    )

    return IntegrationStatusResponse(
        connected=conn.status == IntegrationStatus.ACTIVE.value,
        provider=conn.provider,
        status=conn.status,
        last_synced_at=conn.last_synced_at,
        last_cursor=conn.last_cursor,
        recent_runs=[IntegrationSyncRunResponse.model_validate(r) for r in recent_runs],
    )


@router.post("/open-dental/upload", response_model=CSVUploadResponse)
async def upload_csv(
    claims_file: UploadFile = File(...),
    lines_file: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_practice_manager),
):
    practice_id = current_user.practice_id

    claims_content = (await claims_file.read()).decode("utf-8")
    try:
        claim_rows = parse_claims_csv(claims_content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    line_rows = None
    if lines_file:
        lines_content = (await lines_file.read()).decode("utf-8")
        try:
            line_rows = parse_lines_csv(lines_content)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    try:
        external_claims = build_external_claims(claim_rows, line_rows)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV data: {str(e)}")

    conn = _get_or_create_connection(db, practice_id)

    run = IntegrationSyncRun(
        connection_id=conn.id,
        practice_id=practice_id,
        provider=IntegrationProvider.OPEN_DENTAL.value,
        status=SyncRunStatus.RUNNING.value,
        sync_type="CSV_UPLOAD",
        pulled_count=len(external_claims),
    )
    db.add(run)
    db.flush()

    import time as _time
    _t0 = _time.monotonic()
    try:
        summary = ingest_external_claims(
            db=db,
            practice_id=practice_id,
            external_claims=external_claims,
            source="OPEN_DENTAL",
            actor_user_id=current_user.id,
        )

        run.status = SyncRunStatus.SUCCEEDED.value
        run.ended_at = datetime.utcnow()
        run.upserted_count = summary.created + summary.updated

        conn.last_synced_at = datetime.utcnow()
        if conn.status == IntegrationStatus.INACTIVE.value:
            conn.status = IntegrationStatus.ACTIVE.value

        db.commit()

        _dur = _time.monotonic() - _t0
        logger.info(
            "[csv_upload] practice_id=%s run_id=%s duration=%.2fs pulled=%d created=%d updated=%d skipped=%d",
            practice_id, run.id, _dur, len(external_claims), summary.created, summary.updated, summary.skipped,
        )
        return CSVUploadResponse(sync_run_id=run.id, summary=summary)

    except Exception as e:
        import json
        _dur = _time.monotonic() - _t0
        run.status = SyncRunStatus.FAILED.value
        run.ended_at = datetime.utcnow()
        run.error_json = json.dumps({"error": str(e)})
        conn.status = IntegrationStatus.ERROR.value
        db.commit()
        logger.error(
            "[csv_upload] FAILED practice_id=%s run_id=%s duration=%.2fs error=%s",
            practice_id, run.id, _dur, str(e),
        )
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


@router.post("/open-dental/sync", response_model=CSVUploadResponse)
def run_sync(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_user),
):
    practice_id = current_user.practice_id
    if not practice_id:
        raise HTTPException(status_code=400, detail="User not associated with a practice")

    conn = db.query(IntegrationConnection).filter(
        IntegrationConnection.practice_id == practice_id,
        IntegrationConnection.provider == IntegrationProvider.OPEN_DENTAL.value,
    ).first()

    if not conn:
        raise HTTPException(status_code=404, detail="No Open Dental integration configured for this practice")

    provider = OpenDentalProvider(
        config_json=conn.config_json,
        secrets_ref=conn.secrets_ref,
    )

    run = IntegrationSyncRun(
        connection_id=conn.id,
        practice_id=practice_id,
        provider=IntegrationProvider.OPEN_DENTAL.value,
        status=SyncRunStatus.RUNNING.value,
        sync_type="API",
    )
    db.add(run)
    db.flush()

    import time as _time
    _t0 = _time.monotonic()
    try:
        claims, next_cursor = provider.fetch_updated_claims(cursor=conn.last_cursor)
        run.pulled_count = len(claims)

        summary = ingest_external_claims(
            db=db,
            practice_id=practice_id,
            external_claims=claims,
            source="OPEN_DENTAL",
            actor_user_id=current_user.id,
        )

        run.status = SyncRunStatus.SUCCEEDED.value
        run.ended_at = datetime.utcnow()
        run.upserted_count = summary.created + summary.updated

        if next_cursor:
            conn.last_cursor = next_cursor
        conn.last_synced_at = datetime.utcnow()
        conn.status = IntegrationStatus.ACTIVE.value

        db.commit()
        _dur = _time.monotonic() - _t0
        logger.info(
            "[api_sync] practice_id=%s run_id=%s duration=%.2fs pulled=%d created=%d updated=%d skipped=%d",
            practice_id, run.id, _dur, len(claims), summary.created, summary.updated, summary.skipped,
        )
        return CSVUploadResponse(sync_run_id=run.id, summary=summary)

    except OpenDentalNotConfigured as e:
        import json
        _dur = _time.monotonic() - _t0
        run.status = SyncRunStatus.FAILED.value
        run.ended_at = datetime.utcnow()
        run.error_json = json.dumps({"error": str(e)})
        db.commit()
        logger.warning("[api_sync] NOT_CONFIGURED practice_id=%s run_id=%s duration=%.2fs", practice_id, run.id, _dur)
        raise HTTPException(status_code=422, detail=str(e))

    except Exception as e:
        import json
        _dur = _time.monotonic() - _t0
        run.status = SyncRunStatus.FAILED.value
        run.ended_at = datetime.utcnow()
        run.error_json = json.dumps({"error": str(e)})
        conn.status = IntegrationStatus.ERROR.value
        db.commit()
        logger.error(
            "[api_sync] FAILED practice_id=%s run_id=%s duration=%.2fs error=%s",
            practice_id, run.id, _dur, str(e),
        )
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@router.get("/open-dental/runs", response_model=List[IntegrationSyncRunResponse])
def list_sync_runs(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_practice_manager),
):
    practice_id = current_user.practice_id
    runs = (
        db.query(IntegrationSyncRun)
        .filter(IntegrationSyncRun.practice_id == practice_id)
        .order_by(IntegrationSyncRun.started_at.desc())
        .limit(20)
        .all()
    )
    return runs

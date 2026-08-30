"""
Google Sheets Router — CRUD for sync configurations, trigger manual sync, view sync history and errors.
Managers and Admins have full access.
"""
import uuid
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, Body
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from app.auth.dependencies import require_data_ops_or_above
from app.database import get_db
from app.models.integrations import GoogleSheetsSyncConfig, GoogleSheetsSyncRun, SyncErrorLog
from app.models.user import User
from app.core.exceptions import NotFoundError
from app.integrations.google_sheets.service import GoogleSheetsSyncService

router = APIRouter(prefix="/integrations/google-sheets", tags=["Google Sheets Integration"])


class SyncConfigCreateBody(BaseModel):
    name: str
    spreadsheet_id: str
    sheet_name: str = "Sheet1"
    range: str = "A:Z"
    column_mapping: Dict[str, str] = {
        "first_name": "First Name",
        "last_name": "Last Name",
        "email": "Email",
        "phone": "Phone",
        "company": "Company",
        "position": "Position",
        "country": "Country",
        "industry": "Industry",
        "source": "Source",
    }
    campaign_id: Optional[str] = None
    sync_every_minutes: int = 60
    is_active: bool = True


class MockSyncTriggerBody(BaseModel):
    mock_data: Optional[List[Dict[str, Any]]] = None


@router.get("/configs")
async def list_configs(
    current_user: User = Depends(require_data_ops_or_above),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(GoogleSheetsSyncConfig).order_by(GoogleSheetsSyncConfig.created_at.desc())
    configs = (await db.execute(stmt)).scalars().all()
    return {
        "data": [
            {
                "id": str(c.id),
                "name": c.name,
                "spreadsheet_id": c.spreadsheet_id,
                "sheet_name": c.sheet_name,
                "range": c.range,
                "column_mapping": c.column_mapping,
                "sync_every_minutes": c.sync_every_minutes,
                "is_active": c.is_active,
                "last_synced_at": c.last_synced_at.isoformat() if c.last_synced_at else None,
                "created_at": c.created_at.isoformat(),
            }
            for c in configs
        ]
    }


@router.post("/configs", status_code=201)
async def create_config(
    body: SyncConfigCreateBody,
    current_user: User = Depends(require_data_ops_or_above),
    db: AsyncSession = Depends(get_db),
):
    cfg = GoogleSheetsSyncConfig(
        name=body.name,
        spreadsheet_id=body.spreadsheet_id,
        sheet_name=body.sheet_name,
        range=body.range,
        column_mapping=body.column_mapping,
        campaign_id=uuid.UUID(body.campaign_id) if body.campaign_id else None,
        sync_every_minutes=body.sync_every_minutes,
        is_active=body.is_active,
        created_by=current_user.id,
    )
    db.add(cfg)
    await db.flush()
    return {
        "data": {
            "id": str(cfg.id),
            "name": cfg.name,
            "spreadsheet_id": cfg.spreadsheet_id,
        }
    }


@router.post("/sync/{config_id}")
async def trigger_sync(
    config_id: uuid.UUID,
    body: MockSyncTriggerBody = Body(default=MockSyncTriggerBody()),
    current_user: User = Depends(require_data_ops_or_above),
    db: AsyncSession = Depends(get_db),
):
    """Trigger an immediate synchronization for a Google Sheet config."""
    service = GoogleSheetsSyncService(db)
    run = await service.run_sync(
        config_id=config_id,
        triggered_by="manual",
        triggered_by_user_id=current_user.id,
        mock_data=body.mock_data,
    )
    return {
        "message": f"Sync {run.status.lower()}",
        "data": {
            "run_id": str(run.id),
            "status": run.status,
            "rows_read": run.rows_read,
            "rows_imported": run.rows_imported,
            "rows_duplicate": run.rows_duplicate,
            "rows_error": run.rows_error,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        },
    }


@router.get("/runs")
async def list_sync_runs(
    config_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    current_user: User = Depends(require_data_ops_or_above),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(GoogleSheetsSyncRun).options(selectinload(GoogleSheetsSyncRun.config))
    if config_id:
        stmt = stmt.where(GoogleSheetsSyncRun.config_id == uuid.UUID(config_id))

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(GoogleSheetsSyncRun.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    runs = (await db.execute(stmt)).scalars().all()

    return {
        "data": [
            {
                "id": str(r.id),
                "config_id": str(r.config_id),
                "config_name": r.config.name if r.config else None,
                "status": r.status,
                "triggered_by": r.triggered_by,
                "rows_read": r.rows_read,
                "rows_imported": r.rows_imported,
                "rows_duplicate": r.rows_duplicate,
                "rows_error": r.rows_error,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                "error_message": r.error_message,
            }
            for r in runs
        ],
        "meta": {"total": total, "page": page, "per_page": per_page},
    }


@router.get("/errors")
async def list_sync_errors(
    run_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    current_user: User = Depends(require_data_ops_or_above),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(SyncErrorLog)
    if run_id:
        stmt = stmt.where(SyncErrorLog.sync_run_id == uuid.UUID(run_id))
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(SyncErrorLog.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    errors = (await db.execute(stmt)).scalars().all()

    return {
        "data": [
            {
                "id": str(e.id),
                "sync_run_id": str(e.sync_run_id),
                "row_index": e.row_index,
                "field_name": e.field_name,
                "error_message": e.error_message,
                "raw_value": e.raw_value,
                "created_at": e.created_at.isoformat(),
            }
            for e in errors
        ],
        "meta": {"total": total, "page": page, "per_page": per_page},
    }

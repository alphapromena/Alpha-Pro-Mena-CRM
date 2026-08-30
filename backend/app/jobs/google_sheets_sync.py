"""
Background job: Scheduled Google Sheets periodic synchronization.
"""
from datetime import datetime, timezone
import structlog
from sqlalchemy import select
from app.database import get_db_context
from app.models.integrations import GoogleSheetsSyncConfig
from app.integrations.google_sheets.service import GoogleSheetsSyncService

logger = structlog.get_logger(__name__)


async def run_scheduled_sheets_sync():
    """Finds active Google Sheets sync configurations and triggers sync."""
    async with get_db_context() as db:
        stmt = select(GoogleSheetsSyncConfig).where(GoogleSheetsSyncConfig.is_active.is_(True))
        configs = (await db.execute(stmt)).scalars().all()
        if not configs:
            return

        service = GoogleSheetsSyncService(db)
        for cfg in configs:
            try:
                await service.run_sync(config_id=cfg.id, triggered_by="scheduler")
            except Exception as e:
                logger.error("jobs.scheduled_sync_error", config_id=str(cfg.id), error=str(e))

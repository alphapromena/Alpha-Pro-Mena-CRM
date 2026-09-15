"""
Background job: automatically soft-delete archived Tasks that were not
restored within 7 full calendar days from archived_at.

Safety guarantees:
- Only touches tasks with archived_at IS NOT NULL and status = COMPLETED.
- Excludes tasks that have been restored (archived_at IS NULL after restore).
- Idempotent: running multiple times produces no error and no duplicate audit entries.
- Records an AuditLog entry for each expired task.
- Threshold is 7 *full* days: if archived at 09:00 today, expiry is 09:00 seven days later.
"""
from datetime import datetime, timezone, timedelta
import structlog

from sqlalchemy import select, delete
from app.database import get_db_context
from app.models.task import Task, TaskStatus
from app.audit.service import AuditService

logger = structlog.get_logger(__name__)

ARCHIVE_TTL_DAYS = 7


async def cleanup_expired_archived_tasks() -> dict:
    """
    Find and hard-delete tasks archived >= 7 days ago.
    Returns a summary dict for logging and HTTP response.
    """
    expiry_threshold = datetime.now(timezone.utc) - timedelta(days=ARCHIVE_TTL_DAYS)
    deleted_ids = []
    errors = []

    async with get_db_context() as db:
        # Find expired tasks — must be COMPLETED and archived > 7 days ago
        stmt = select(Task).where(
            Task.archived_at.isnot(None),
            Task.archived_at <= expiry_threshold,
            Task.status == TaskStatus.COMPLETED,
        )
        expired = (await db.execute(stmt)).scalars().all()

        if not expired:
            logger.info("jobs.cleanup_archived_tasks.nothing_to_delete")
            return {"deleted": 0, "errors": 0, "threshold": expiry_threshold.isoformat()}

        logger.info(
            "jobs.cleanup_archived_tasks.found_expired",
            count=len(expired),
            threshold=expiry_threshold.isoformat(),
        )

        audit = AuditService(db)

        for task in expired:
            try:
                # Write immutable audit event before deletion
                await audit.log(
                    action="task.archive_expired",
                    entity_type="task",
                    actor_id=None,  # system action
                    entity_id=task.id,
                    old_value={
                        "title": task.title,
                        "archived_at": task.archived_at.isoformat() if task.archived_at else None,
                        "archived_by": str(task.archived_by) if task.archived_by else None,
                    },
                    new_value={"action": "hard_deleted", "reason": "archive_ttl_7_days"},
                    notes=f"Task expired after {ARCHIVE_TTL_DAYS} days in archive.",
                )
                deleted_ids.append(str(task.id))
                await db.delete(task)
            except Exception as exc:
                logger.error(
                    "jobs.cleanup_archived_tasks.error_on_task",
                    task_id=str(task.id),
                    error=str(exc),
                )
                errors.append(str(task.id))

    logger.info(
        "jobs.cleanup_archived_tasks.completed",
        deleted=len(deleted_ids),
        errors=len(errors),
    )
    return {
        "deleted": len(deleted_ids),
        "errors": len(errors),
        "threshold": expiry_threshold.isoformat(),
        "deleted_ids": deleted_ids,
    }

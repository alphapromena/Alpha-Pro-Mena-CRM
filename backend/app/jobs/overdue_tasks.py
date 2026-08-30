"""
Background job: Check and update overdue tasks, send notifications.
"""
from datetime import datetime, timezone
import structlog
from sqlalchemy import select, update
from app.database import get_db_context
from app.models.task import Task, TaskStatus
from app.models.notification import Notification

logger = structlog.get_logger(__name__)


async def check_overdue_tasks():
    """Finds tasks with due_at in the past that are still OPEN or IN_PROGRESS."""
    now = datetime.now(timezone.utc)
    async with get_db_context() as db:
        stmt = (
            select(Task)
            .where(
                Task.due_at < now,
                Task.status.in_([TaskStatus.OPEN, TaskStatus.IN_PROGRESS]),
            )
        )
        tasks = (await db.execute(stmt)).scalars().all()
        if not tasks:
            return

        logger.info("jobs.check_overdue_tasks", count=len(tasks))

        for task in tasks:
            task.status = TaskStatus.OVERDUE
            db.add(task)

            # Send in-app notification to assignee if not already notified
            if task.assigned_to:
                notif = Notification(
                    user_id=task.assigned_to,
                    type="TASK_OVERDUE",
                    title="Task Overdue",
                    message=f"Task '{task.title}' is overdue.",
                    entity_type="task",
                    entity_id=task.id,
                )
                db.add(notif)

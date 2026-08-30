"""
APScheduler background jobs scheduler management.
"""
import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import get_settings
from app.jobs.overdue_tasks import check_overdue_tasks
from app.jobs.recall_reminder import check_recall_reminders
from app.jobs.google_sheets_sync import run_scheduled_sheets_sync

logger = structlog.get_logger(__name__)
settings = get_settings()

scheduler = AsyncIOScheduler()


async def start_scheduler():
    """Register all recurring cron/interval jobs and start the scheduler."""
    if scheduler.running:
        return

    # 1. Overdue Tasks Checker (every 5 mins by default)
    scheduler.add_job(
        check_overdue_tasks,
        trigger=IntervalTrigger(minutes=settings.job_overdue_task_check_minutes),
        id="check_overdue_tasks",
        replace_existing=True,
    )

    # 2. Recall Reminders (every 15 mins)
    scheduler.add_job(
        check_recall_reminders,
        trigger=IntervalTrigger(minutes=15),
        id="check_recall_reminders",
        replace_existing=True,
    )

    # 3. Google Sheets Scheduled Sync (every 15-60 mins)
    scheduler.add_job(
        run_scheduled_sheets_sync,
        trigger=IntervalTrigger(minutes=settings.job_google_sheets_sync_minutes),
        id="run_scheduled_sheets_sync",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("scheduler.started", jobs=[job.id for job in scheduler.get_jobs()])


async def stop_scheduler():
    """Gracefully shutdown scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("scheduler.stopped")

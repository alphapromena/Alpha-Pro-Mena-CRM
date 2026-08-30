"""
Jobs router — HTTP triggers for the background jobs.

On long-running servers APScheduler runs these on a timer. On serverless (Vercel) there
is no resident process, so Vercel Cron calls these endpoints instead, authenticating
with `Authorization: Bearer $CRON_SECRET` (Vercel adds that header automatically).
"""
import secrets
from typing import Awaitable, Callable, Dict

import structlog
from fastapi import APIRouter, Request

from app.config import get_settings
from app.core.exceptions import ForbiddenError, NotFoundError, UnauthorizedError
from app.jobs.google_sheets_sync import run_scheduled_sheets_sync
from app.jobs.overdue_tasks import check_overdue_tasks
from app.jobs.recall_reminder import check_recall_reminders

logger = structlog.get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/jobs", tags=["Jobs"])

JOBS: Dict[str, Callable[[], Awaitable[None]]] = {
    "overdue-tasks": check_overdue_tasks,
    "recall-reminders": check_recall_reminders,
    "sheets-sync": run_scheduled_sheets_sync,
}


def _authorize(request: Request) -> None:
    if not settings.cron_secret:
        raise ForbiddenError("Job endpoints are disabled: CRON_SECRET is not configured.")
    header = request.headers.get("authorization", "")
    token = header[7:].strip() if header.lower().startswith("bearer ") else ""
    if not token or not secrets.compare_digest(token, settings.cron_secret):
        raise UnauthorizedError("Invalid cron token.")


async def _run(name: str) -> dict:
    try:
        await JOBS[name]()
        logger.info("jobs.http_trigger.completed", job=name)
        return {"job": name, "status": "ok"}
    except Exception as exc:  # keep the other jobs running; report per-job status
        logger.error("jobs.http_trigger.failed", job=name, error=str(exc))
        return {"job": name, "status": "error", "error": str(exc)}


@router.api_route("/run-all", methods=["GET", "POST"])
async def run_all_jobs(request: Request):
    """Run every background job once (single Vercel Cron entry)."""
    _authorize(request)
    return {"results": [await _run(name) for name in JOBS]}


@router.api_route("/{job_name}", methods=["GET", "POST"])
async def run_job(job_name: str, request: Request):
    """Run one background job: overdue-tasks | recall-reminders | sheets-sync."""
    _authorize(request)
    if job_name not in JOBS:
        raise NotFoundError(f"Unknown job '{job_name}'. Available: {', '.join(JOBS)}.")
    return await _run(job_name)

"""
Background job: Check upcoming recalls and notify sales agents 15-30m in advance.
"""
from datetime import datetime, timezone, timedelta
import structlog
from sqlalchemy import select
from app.database import get_db_context
from app.models.recall import Recall
from app.models.notification import Notification

logger = structlog.get_logger(__name__)


async def check_recall_reminders():
    now = datetime.now(timezone.utc)
    window = now + timedelta(minutes=30)

    async with get_db_context() as db:
        stmt = (
            select(Recall)
            .where(
                Recall.scheduled_at >= now,
                Recall.scheduled_at <= window,
                Recall.status == "PENDING",
            )
        )
        recalls = (await db.execute(stmt)).scalars().all()
        if not recalls:
            return

        for r in recalls:
            if r.user_id:
                notif = Notification(
                    user_id=r.user_id,
                    type="RECALL_REMINDER",
                    title="Upcoming Recall Callback",
                    message=f"You have a scheduled call-back at {r.scheduled_at.strftime('%H:%M UTC')}.",
                    entity_type="recall",
                    entity_id=r.id,
                )
                db.add(notif)

"""
Tasks router — full team task management, filtering, completion, archiving, and reassignment with audit logging.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.task import Task, TaskStatus, TaskType
from app.models.user import User
from app.models.audit import AuditLog
from app.audit.service import AuditService
from app.core.exceptions import NotFoundError, ForbiddenError

router = APIRouter(prefix="/tasks", tags=["Tasks"])


class TaskCreateBody(BaseModel):
    title: str
    description: Optional[str] = None
    contact_id: Optional[str] = None
    company_id: Optional[str] = None
    assigned_to: Optional[str] = None
    type: str = "CALL"
    priority: str = "MEDIUM"
    due_at: Optional[str] = None


class TaskCompleteBody(BaseModel):
    completion_notes: Optional[str] = None


class TaskArchiveBody(BaseModel):
    """Body for the archive action (no fields required, but allows future extensions)."""
    pass


def _get_task_category(t: Task) -> str:
    """Classify task into 1 of 3 required categories."""
    if t.type in ["EMAIL", "WHATSAPP"]:
        return "COMMUNICATION"
    if t.created_by and t.assigned_to and str(t.created_by) != str(t.assigned_to) and t.type == "OTHER":
        return "INTERNAL_ASSIGNED"
    if t.created_by and t.assigned_to and str(t.created_by) != str(t.assigned_to):
        return "INTERNAL_ASSIGNED"
    if t.type in ["CALL", "RECALL", "FOLLOW_UP", "PROPOSAL", "DEMO", "MEETING"]:
        return "CUSTOMER_ACTION"
    return "INTERNAL_ASSIGNED"


def _task_dict(t: Task) -> dict:
    # Deletion deadline = 7 days after archived_at
    deletion_deadline = None
    if t.archived_at:
        from datetime import timedelta
        deadline_dt = t.archived_at + timedelta(days=7)
        deletion_deadline = deadline_dt.isoformat()

    return {
        "id": str(t.id),
        "title": t.title,
        "description": t.description,
        "contact_id": str(t.contact_id) if t.contact_id else None,
        "contact_name": t.contact.full_name if t.contact else None,
        "company_id": str(t.company_id) if t.company_id else None,
        "company_name": t.company.name if t.company else None,
        "assigned_to": str(t.assigned_to) if t.assigned_to else None,
        "assignee_name": t.assignee.full_name if t.assignee else None,
        "created_by": str(t.created_by) if t.created_by else None,
        "creator_name": t.creator.full_name if t.creator else None,
        "category": _get_task_category(t),
        "type": t.type,
        "priority": t.priority,
        "status": t.status,
        "due_at": t.due_at.isoformat() if t.due_at else None,
        "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        "completion_notes": t.completion_notes,
        "archived_at": t.archived_at.isoformat() if t.archived_at else None,
        "archived_by": str(t.archived_by) if t.archived_by else None,
        "archiver_name": t.archiver.full_name if hasattr(t, 'archiver') and t.archiver else None,
        "deletion_deadline": deletion_deadline,
        "created_at": t.created_at.isoformat(),
    }


def _base_task_query():
    return (
        select(Task)
        .options(
            selectinload(Task.contact),
            selectinload(Task.assignee),
            selectinload(Task.creator),
            selectinload(Task.company),
            selectinload(Task.archiver),
        )
    )


@router.get("")
async def list_tasks(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    status: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    assigned_to: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    contact_id: Optional[str] = Query(None),
    company_id: Optional[str] = Query(None),
    overdue_only: bool = Query(False),
    # archived=false (default) → active tasks only (archived_at IS NULL)
    # archived=true → only archived tasks
    archived: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = _base_task_query()

    # Archived filter: active tasks exclude archived ones
    if archived:
        stmt = stmt.where(Task.archived_at.isnot(None))
    else:
        stmt = stmt.where(Task.archived_at.is_(None))

    # Role scoping: Manager and above see all team tasks. Sales user sees assigned only.
    target_user_filter = assigned_to or user_id
    if not current_user.is_manager_or_above:
        stmt = stmt.where(Task.assigned_to == current_user.id)
    elif target_user_filter:
        try:
            stmt = stmt.where(Task.assigned_to == uuid.UUID(target_user_filter))
        except Exception:
            pass

    if status:
        stmt = stmt.where(Task.status == status)
    if type:
        stmt = stmt.where(Task.type == type)
    if priority:
        stmt = stmt.where(Task.priority == priority.strip().upper())
    if contact_id:
        try:
            stmt = stmt.where(Task.contact_id == uuid.UUID(contact_id))
        except Exception:
            pass
    if company_id:
        try:
            stmt = stmt.where(Task.company_id == uuid.UUID(company_id))
        except Exception:
            pass
    if overdue_only:
        now = datetime.now(timezone.utc)
        stmt = stmt.where(
            Task.due_at < now,
            Task.status.in_([TaskStatus.OPEN, TaskStatus.IN_PROGRESS, TaskStatus.OVERDUE]),
        )

    # Category filtering
    if category == "COMMUNICATION":
        stmt = stmt.where(Task.type.in_(["EMAIL", "WHATSAPP"]))
    elif category == "CUSTOMER_ACTION":
        stmt = stmt.where(Task.type.in_(["CALL", "RECALL", "FOLLOW_UP", "PROPOSAL", "DEMO", "MEETING"]))
    elif category == "INTERNAL_ASSIGNED":
        stmt = stmt.where(
            or_(
                Task.type == "OTHER",
                Task.created_by != Task.assigned_to,
            )
        )

    total = (await db.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))).scalar_one()
    stmt = stmt.order_by(Task.due_at.asc().nullslast(), Task.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    tasks = (await db.execute(stmt)).scalars().all()

    return {"data": [_task_dict(t) for t in tasks], "meta": {"total": total, "page": page, "per_page": per_page}}


@router.post("", status_code=201)
async def create_task(
    body: TaskCreateBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    due = None
    if body.due_at:
        try:
            clean_due = body.due_at.replace("Z", "+00:00") if body.due_at.endswith("Z") else body.due_at
            due = datetime.fromisoformat(clean_due)
        except Exception:
            due = None

    assigned_target = current_user.id
    if body.assigned_to:
        try:
            assigned_target = uuid.UUID(body.assigned_to)
        except Exception:
            assigned_target = current_user.id

    contact_uuid = None
    if body.contact_id:
        try:
            contact_uuid = uuid.UUID(body.contact_id)
        except Exception:
            contact_uuid = None

    company_uuid = None
    if body.company_id:
        try:
            company_uuid = uuid.UUID(body.company_id)
        except Exception:
            company_uuid = None

    task = Task(
        title=body.title,
        description=body.description,
        contact_id=contact_uuid,
        company_id=company_uuid,
        assigned_to=assigned_target,
        created_by=current_user.id,
        type=body.type.upper() if body.type else "CALL",
        priority=body.priority.upper() if body.priority else "MEDIUM",
        status=TaskStatus.OPEN,
        due_at=due,
    )
    db.add(task)
    await db.flush()

    # Re-fetch with relations
    stmt = _base_task_query().where(Task.id == task.id)
    loaded = (await db.execute(stmt)).scalar_one()
    return {"data": _task_dict(loaded)}


@router.get("/{task_id}")
async def get_task(
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = _base_task_query().where(Task.id == task_id)
    task = (await db.execute(stmt)).scalar_one_or_none()
    if not task:
        raise NotFoundError("Task not found.")
    if not current_user.is_manager_or_above and str(task.assigned_to) != str(current_user.id):
        raise ForbiddenError("Access denied.")
    return {"data": _task_dict(task)}


@router.post("/{task_id}/complete")
async def complete_task(
    task_id: uuid.UUID,
    body: TaskCompleteBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = _base_task_query().where(Task.id == task_id)
    task = (await db.execute(stmt)).scalar_one_or_none()
    if not task:
        raise NotFoundError("Task not found.")
    if not current_user.is_manager_or_above and str(task.assigned_to) != str(current_user.id):
        raise ForbiddenError("Access denied.")

    task.status = TaskStatus.COMPLETED
    task.completed_at = datetime.now(timezone.utc)
    task.completion_notes = body.completion_notes
    db.add(task)
    await db.flush()
    return {"data": _task_dict(task)}


@router.post("/{task_id}/archive")
async def archive_task(
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Archive a completed Task. Only COMPLETED tasks can be archived.
    Sets archived_at and archived_by. The task disappears from active counters.
    Auto-cleanup job will hard-delete it if not restored within 7 days.
    """
    stmt = _base_task_query().where(Task.id == task_id)
    task = (await db.execute(stmt)).scalar_one_or_none()
    if not task:
        raise NotFoundError("Task not found.")
    if not current_user.is_manager_or_above and str(task.assigned_to) != str(current_user.id):
        raise ForbiddenError("Access denied.")
    if task.status != TaskStatus.COMPLETED:
        from app.core.exceptions import ValidationError
        raise ValidationError("Only completed tasks can be archived.")
    if task.archived_at is not None:
        from app.core.exceptions import ValidationError
        raise ValidationError("Task is already archived.")

    task.archived_at = datetime.now(timezone.utc)
    task.archived_by = current_user.id
    db.add(task)
    await db.flush()

    audit = AuditService(db)
    await audit.log(
        action="task.archived",
        entity_type="task",
        actor_id=current_user.id,
        entity_id=task.id,
        new_value={"archived_at": task.archived_at.isoformat(), "archived_by": str(current_user.id)},
    )

    return {"data": _task_dict(task)}


@router.post("/{task_id}/restore")
async def restore_task(
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Restore an archived Task. Clears archived_at and archived_by, resetting the 7-day timer.
    """
    stmt = _base_task_query().where(Task.id == task_id)
    task = (await db.execute(stmt)).scalar_one_or_none()
    if not task:
        raise NotFoundError("Task not found.")
    if not current_user.is_manager_or_above and str(task.assigned_to) != str(current_user.id):
        raise ForbiddenError("Access denied.")
    if task.archived_at is None:
        from app.core.exceptions import ValidationError
        raise ValidationError("Task is not archived.")

    old_archived_at = task.archived_at.isoformat()
    task.archived_at = None
    task.archived_by = None
    db.add(task)
    await db.flush()

    audit = AuditService(db)
    await audit.log(
        action="task.restored",
        entity_type="task",
        actor_id=current_user.id,
        entity_id=task.id,
        old_value={"archived_at": old_archived_at},
        new_value={"archived_at": None, "restored_by": str(current_user.id)},
    )

    return {"data": _task_dict(task)}


@router.patch("/{task_id}")
async def update_task(
    task_id: uuid.UUID,
    body: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = _base_task_query().where(Task.id == task_id)
    task = (await db.execute(stmt)).scalar_one_or_none()
    if not task:
        raise NotFoundError("Task not found.")

    if not current_user.is_manager_or_above and str(task.assigned_to) != str(current_user.id):
        raise ForbiddenError("Access denied.")

    old_values = {
        "title": task.title,
        "assigned_to": str(task.assigned_to) if task.assigned_to else None,
        "priority": task.priority,
        "status": task.status,
        "due_at": task.due_at.isoformat() if task.due_at else None,
    }

    reassigned = False
    if "assigned_to" in body and body["assigned_to"]:
        new_assigned_uid = uuid.UUID(body["assigned_to"])
        if new_assigned_uid != task.assigned_to:
            if not current_user.is_manager_or_above:
                raise ForbiddenError("Only managers and above can reassign tasks.")
            task.assigned_to = new_assigned_uid
            reassigned = True

    for field in ["title", "description", "status", "priority", "type"]:
        if field in body and body[field] is not None:
            setattr(task, field, body[field])

    if "due_at" in body:
        task.due_at = datetime.fromisoformat(body["due_at"]) if body["due_at"] else None

    db.add(task)
    await db.flush()

    # Immutable Audit Log on reassignment or major changes
    if reassigned or "priority" in body or "status" in body:
        audit = AuditService(db)
        action_name = "task.reassigned" if reassigned else "task.updated"
        await audit.log(
            action=action_name,
            entity_type="task",
            actor_id=current_user.id,
            entity_id=task.id,
            old_value=old_values,
            new_value={
                "title": task.title,
                "assigned_to": str(task.assigned_to) if task.assigned_to else None,
                "priority": task.priority,
                "status": task.status,
                "due_at": task.due_at.isoformat() if task.due_at else None,
            },
        )

    # Re-fetch for updated assignee relationship
    reloaded = (await db.execute(stmt)).scalar_one()
    return {"data": _task_dict(reloaded)}

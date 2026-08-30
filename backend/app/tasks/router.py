"""
Tasks router — full team task management, filtering, completion, and reassignment with audit logging.
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
        "created_at": t.created_at.isoformat(),
    }


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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Task)
        .options(
            selectinload(Task.contact),
            selectinload(Task.assignee),
            selectinload(Task.creator),
            selectinload(Task.company),
        )
    )
    # Role scoping: Manager and above see all team tasks. Sales user sees assigned only.
    target_user_filter = assigned_to or user_id
    if not current_user.is_manager_or_above:
        stmt = stmt.where(Task.assigned_to == current_user.id)
    elif target_user_filter:
        stmt = stmt.where(Task.assigned_to == uuid.UUID(target_user_filter))

    if status:
        stmt = stmt.where(Task.status == status)
    if type:
        stmt = stmt.where(Task.type == type)
    if priority:
        stmt = stmt.where(Task.priority == priority.upper())
    if contact_id:
        stmt = stmt.where(Task.contact_id == uuid.UUID(contact_id))
    if company_id:
        stmt = stmt.where(Task.company_id == uuid.UUID(company_id))
    if overdue_only:
        stmt = stmt.where(
            Task.due_at < datetime.now(timezone.utc),
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

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(Task.due_at.asc().nullslast(), Task.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    tasks = (await db.execute(stmt)).scalars().all()

    return {"data": [_task_dict(t) for t in tasks], "meta": {"total": total, "page": page, "per_page": per_page}}


@router.post("", status_code=201)
async def create_task(
    body: TaskCreateBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    due = datetime.fromisoformat(body.due_at) if body.due_at else None
    assigned_target = uuid.UUID(body.assigned_to) if body.assigned_to else current_user.id
    task = Task(
        title=body.title,
        description=body.description,
        contact_id=uuid.UUID(body.contact_id) if body.contact_id else None,
        company_id=uuid.UUID(body.company_id) if body.company_id else None,
        assigned_to=assigned_target,
        created_by=current_user.id,
        type=body.type,
        priority=body.priority,
        status=TaskStatus.OPEN,
        due_at=due,
    )
    db.add(task)
    await db.flush()

    # Re-fetch with relations
    stmt = select(Task).where(Task.id == task.id).options(
        selectinload(Task.contact), selectinload(Task.assignee), selectinload(Task.creator), selectinload(Task.company)
    )
    loaded = (await db.execute(stmt)).scalar_one()
    return {"data": _task_dict(loaded)}


@router.get("/{task_id}")
async def get_task(
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Task)
        .where(Task.id == task_id)
        .options(selectinload(Task.contact), selectinload(Task.assignee), selectinload(Task.creator), selectinload(Task.company))
    )
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
    stmt = (
        select(Task)
        .where(Task.id == task_id)
        .options(selectinload(Task.contact), selectinload(Task.assignee), selectinload(Task.creator), selectinload(Task.company))
    )
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


@router.patch("/{task_id}")
async def update_task(
    task_id: uuid.UUID,
    body: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Task)
        .where(Task.id == task_id)
        .options(selectinload(Task.contact), selectinload(Task.assignee), selectinload(Task.creator), selectinload(Task.company))
    )
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

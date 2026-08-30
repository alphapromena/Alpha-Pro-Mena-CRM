"""
Automation service — event-driven rule execution engine.
Reads rules from DB, evaluates conditions, executes actions idempotently.
"""
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.automation import AutomationExecution, AutomationRule
from app.models.user import User

logger = structlog.get_logger(__name__)


class AutomationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def fire_event(
        self,
        event: str,
        entity_id: uuid.UUID,
        entity_type: str,
        payload: Dict[str, Any],
        actor_id: Optional[uuid.UUID] = None,
    ) -> int:
        """
        Fire a CRM event and execute all matching active automation rules.
        Returns count of rules executed.
        """
        # Find all active rules for this trigger event
        stmt = select(AutomationRule).where(
            AutomationRule.trigger_event == event,
            AutomationRule.is_active.is_(True),
        )
        result = await self.db.execute(stmt)
        rules = result.scalars().all()

        executed = 0
        for rule in rules:
            if await self._evaluate_conditions(rule, payload):
                await self._execute_rule(rule, entity_id, entity_type, payload, actor_id)
                executed += 1

        logger.info("automation.event_fired", trigger_event=event, entity_id=str(entity_id), rules_executed=executed)
        return executed

    async def _evaluate_conditions(self, rule: AutomationRule, payload: Dict[str, Any]) -> bool:
        """Evaluate JSONB conditions against event payload."""
        if not rule.conditions:
            return True

        conditions = rule.conditions.get("conditions", [])
        for cond in conditions:
            field = cond.get("field")
            operator = cond.get("operator")
            value = cond.get("value")
            actual = payload.get(field)

            match operator:
                case "eq":
                    if actual != value:
                        return False
                case "neq":
                    if actual == value:
                        return False
                case "gt":
                    if not (actual is not None and actual > value):
                        return False
                case "gte":
                    if not (actual is not None and actual >= value):
                        return False
                case "lt":
                    if not (actual is not None and actual < value):
                        return False
                case "lte":
                    if not (actual is not None and actual <= value):
                        return False
                case "in":
                    if actual not in (value or []):
                        return False
                case "not_in":
                    if actual in (value or []):
                        return False
                case "exists":
                    if value and actual is None:
                        return False

        return True

    async def _execute_rule(
        self,
        rule: AutomationRule,
        entity_id: uuid.UUID,
        entity_type: str,
        payload: Dict[str, Any],
        actor_id: Optional[uuid.UUID],
    ) -> None:
        """Execute a single automation rule with idempotency check."""
        # Generate idempotency key per trigger instance
        event_ref = payload.get("call_id") or payload.get("task_id") or payload.get("note_id") or str(uuid.uuid4())
        key_source = f"{rule.id}:{entity_id}:{rule.trigger_event}:{event_ref}"
        idempotency_key = hashlib.sha256(key_source.encode()).hexdigest()

        # Check if already executed
        existing = await self.db.execute(
            select(AutomationExecution).where(
                AutomationExecution.idempotency_key == idempotency_key,
                AutomationExecution.status.in_(["EXECUTED", "PENDING"]),
            )
        )
        if existing.scalar_one_or_none():
            logger.debug("automation.skipped_duplicate", rule_id=str(rule.id), key=idempotency_key)
            return

        # Record execution attempt
        execution = AutomationExecution(
            rule_id=rule.id,
            trigger_event=rule.trigger_event,
            entity_id=entity_id,
            entity_type=entity_type,
            idempotency_key=idempotency_key,
            status="PENDING",
            scheduled_for=datetime.now(timezone.utc),
        )
        self.db.add(execution)
        await self.db.flush()

        try:
            await self._perform_action(rule, entity_id, entity_type, payload, actor_id)
            execution.status = "EXECUTED"
            execution.executed_at = datetime.now(timezone.utc)
        except Exception as e:
            execution.status = "FAILED"
            execution.error_message = str(e)
            logger.error("automation.execution_failed", rule_id=str(rule.id), error=str(e))

        self.db.add(execution)
        await self.db.flush()

    async def _perform_action(
        self,
        rule: AutomationRule,
        entity_id: uuid.UUID,
        entity_type: str,
        payload: Dict[str, Any],
        actor_id: Optional[uuid.UUID],
    ) -> None:
        """Dispatch to the appropriate action handler."""
        action_type = rule.action_type
        config = rule.action_config

        match action_type:
            case "create_task":
                await self._action_create_task(entity_id, entity_type, payload, config, actor_id)
            case "send_notification":
                await self._action_send_notification(entity_id, payload, config)
            case "update_contact_status":
                await self._action_update_status(entity_id, config)
            case "create_no_answer_entry":
                await self._action_no_answer(entity_id, payload, config)
            case _:
                logger.warning("automation.unknown_action", action_type=action_type)

    async def _action_create_task(
        self, entity_id: uuid.UUID, entity_type: str, payload: dict, config: dict, actor_id: Optional[uuid.UUID]
    ) -> None:
        from datetime import timedelta
        from app.models.task import Task, TaskType, TaskPriority, TaskStatus

        due_offset_hours = config.get("due_offset_hours", 0)
        due_at = datetime.now(timezone.utc) + timedelta(hours=due_offset_hours) if due_offset_hours else None

        assigned_to = None
        if config.get("assign_to") == "lead_owner" and payload.get("owner_id"):
            try:
                assigned_to = uuid.UUID(payload["owner_id"])
            except (ValueError, TypeError):
                pass

        task = Task(
            title=config.get("title", "Automated Task"),
            description=config.get("description"),
            contact_id=entity_id if entity_type == "contact" else None,
            assigned_to=assigned_to or actor_id,
            created_by=actor_id,
            type=config.get("task_type", TaskType.CALL),
            priority=config.get("priority", TaskPriority.MEDIUM),
            status=TaskStatus.OPEN,
            due_at=due_at,
            automation_rule_id=None,
        )
        self.db.add(task)
        await self.db.flush()
        logger.info("automation.task_created", task_id=str(task.id), type=task.type)

    async def _action_send_notification(self, entity_id: uuid.UUID, payload: dict, config: dict) -> None:
        from app.models.notification import Notification
        recipient_id_str = payload.get("owner_id") or payload.get("user_id")
        if not recipient_id_str:
            return
        try:
            recipient_id = uuid.UUID(recipient_id_str)
        except (ValueError, TypeError):
            return

        message = config.get("message_template", "Automated notification")
        notif = Notification(
            user_id=recipient_id,
            type=config.get("notification_type", "AUTOMATION"),
            title=config.get("title", "CRM Notification"),
            message=message,
            entity_type="contact",
            entity_id=entity_id,
        )
        self.db.add(notif)
        await self.db.flush()

    async def _action_update_status(self, entity_id: uuid.UUID, config: dict) -> None:
        from app.models.contact import Contact
        from sqlalchemy import select
        result = await self.db.execute(select(Contact).where(Contact.id == entity_id))
        contact = result.scalar_one_or_none()
        if contact and not contact.is_dnc:
            new_status = config.get("new_status")
            if new_status:
                contact.status = new_status
                self.db.add(contact)
                await self.db.flush()

    async def _action_no_answer(self, entity_id: uuid.UUID, payload: dict, config: dict) -> None:
        from datetime import timedelta
        from app.config import get_settings
        from app.models.no_answer import NoAnswerQueue
        from sqlalchemy import select

        app_settings = get_settings()
        retry_hours = config.get("retry_hours", app_settings.no_answer_retry_hours)  # Default 48 hours

        # Find or create no-answer entry
        stmt = select(NoAnswerQueue).where(
            NoAnswerQueue.contact_id == entity_id,
            NoAnswerQueue.status == "PENDING",
        )
        existing = (await self.db.execute(stmt)).scalar_one_or_none()

        if existing:
            existing.attempt_number += 1
            existing.last_attempt_at = datetime.now(timezone.utc)
            existing.next_attempt_at = datetime.now(timezone.utc) + timedelta(hours=retry_hours)
            self.db.add(existing)
        else:
            owner_id = None
            for key in ["owner_id", "user_id"]:
                if payload.get(key):
                    try:
                        owner_id = uuid.UUID(payload[key])
                        break
                    except (ValueError, TypeError):
                        pass

            entry = NoAnswerQueue(
                contact_id=entity_id,
                user_id=owner_id,
                attempt_number=1,
                last_attempt_at=datetime.now(timezone.utc),
                next_attempt_at=datetime.now(timezone.utc) + timedelta(hours=retry_hours),
                status="PENDING",
            )
            self.db.add(entry)
        await self.db.flush()

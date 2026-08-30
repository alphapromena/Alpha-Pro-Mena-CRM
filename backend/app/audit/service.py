"""
Audit service — append-only log writer.
Called from every service that performs sensitive operations.
"""
import uuid
from typing import Any, Dict, Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog

logger = structlog.get_logger(__name__)


class AuditService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def log(
        self,
        action: str,
        entity_type: str,
        actor_id: Optional[uuid.UUID] = None,
        entity_id: Optional[uuid.UUID] = None,
        old_value: Optional[Dict[str, Any]] = None,
        new_value: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> AuditLog:
        """
        Write an immutable audit log entry.
        This method ONLY inserts — never updates or deletes audit logs.
        """
        entry = AuditLog(
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            old_value=old_value,
            new_value=new_value,
            ip_address=ip_address,
            user_agent=user_agent,
            notes=notes,
        )
        self.db.add(entry)
        await self.db.flush()

        logger.info(
            "audit.logged",
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id else None,
            actor_id=str(actor_id) if actor_id else None,
        )
        return entry

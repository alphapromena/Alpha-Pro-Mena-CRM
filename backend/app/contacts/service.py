"""
Contacts service — the heart of the CRM.
Handles CRUD, DNC, status transitions, duplicate detection, timeline.
"""
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import structlog
from sqlalchemy import or_, select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.audit.service import AuditService
from app.core.exceptions import ConflictError, DNCError, ForbiddenError, NotFoundError, ValidationError
from app.core.security import normalize_email, normalize_phone
from app.models.contact import Contact, ContactStatus, ContactPriority
from app.models.company import Company
from app.models.user import User, UserRole
from app.models.call import Call
from app.models.note import ContactNote
from app.models.no_answer import NoAnswerQueue
from app.models.task import Task, TaskStatus
from app.models.follow_up import FollowUp
from app.automation.service import AutomationService

logger = structlog.get_logger(__name__)

ALLOWED_STATUS_TRANSITIONS = {
    ContactStatus.NEW: [
        ContactStatus.CONTACTED, ContactStatus.UNASSIGNED, ContactStatus.DO_NOT_CONTACT,
        ContactStatus.DUPLICATE,
    ],
    ContactStatus.UNASSIGNED: [ContactStatus.NEW],
    ContactStatus.CONTACTED: [
        ContactStatus.IN_PROGRESS, ContactStatus.INTERESTED, ContactStatus.EMAIL_REQUESTED,
        ContactStatus.WHATSAPP_REQUESTED, ContactStatus.DEMO_SCHEDULED, ContactStatus.NOT_INTERESTED,
        ContactStatus.DO_NOT_CONTACT, ContactStatus.NO_ANSWER, ContactStatus.RECALL_SCHEDULED,
        ContactStatus.LOST,
    ],
    ContactStatus.IN_PROGRESS: [
        ContactStatus.INTERESTED, ContactStatus.EMAIL_REQUESTED, ContactStatus.WHATSAPP_REQUESTED,
        ContactStatus.DEMO_SCHEDULED, ContactStatus.PROPOSAL_SENT, ContactStatus.NEGOTIATION,
        ContactStatus.NOT_INTERESTED, ContactStatus.DO_NOT_CONTACT, ContactStatus.NO_ANSWER,
        ContactStatus.RECALL_SCHEDULED, ContactStatus.LOST, ContactStatus.WON,
    ],
    ContactStatus.INTERESTED: [
        ContactStatus.EMAIL_REQUESTED, ContactStatus.WHATSAPP_REQUESTED, ContactStatus.DEMO_SCHEDULED,
        ContactStatus.PROPOSAL_SENT, ContactStatus.NEGOTIATION, ContactStatus.NOT_INTERESTED,
        ContactStatus.DO_NOT_CONTACT, ContactStatus.WON, ContactStatus.LOST,
    ],
    ContactStatus.NO_ANSWER: [
        ContactStatus.CONTACTED, ContactStatus.IN_PROGRESS, ContactStatus.RECALL_SCHEDULED,
        ContactStatus.DO_NOT_CONTACT, ContactStatus.NOT_INTERESTED,
    ],
    ContactStatus.RECALL_SCHEDULED: [
        ContactStatus.CONTACTED, ContactStatus.IN_PROGRESS, ContactStatus.NOT_INTERESTED,
        ContactStatus.DO_NOT_CONTACT,
    ],
    ContactStatus.EMAIL_REQUESTED: [
        ContactStatus.IN_PROGRESS, ContactStatus.INTERESTED, ContactStatus.DEMO_SCHEDULED,
        ContactStatus.PROPOSAL_SENT, ContactStatus.NOT_INTERESTED,
    ],
    ContactStatus.WHATSAPP_REQUESTED: [
        ContactStatus.IN_PROGRESS, ContactStatus.INTERESTED, ContactStatus.DEMO_SCHEDULED,
        ContactStatus.NOT_INTERESTED,
    ],
    ContactStatus.DEMO_SCHEDULED: [
        ContactStatus.DEMO_DONE, ContactStatus.IN_PROGRESS, ContactStatus.PROPOSAL_SENT,
        ContactStatus.NOT_INTERESTED, ContactStatus.LOST,
    ],
    ContactStatus.DEMO_DONE: [
        ContactStatus.PROPOSAL_SENT, ContactStatus.NEGOTIATION, ContactStatus.WON,
        ContactStatus.LOST, ContactStatus.NOT_INTERESTED,
    ],
    ContactStatus.PROPOSAL_SENT: [
        ContactStatus.NEGOTIATION, ContactStatus.WON, ContactStatus.LOST,
        ContactStatus.NOT_INTERESTED,
    ],
    ContactStatus.NEGOTIATION: [ContactStatus.WON, ContactStatus.LOST],
    ContactStatus.WON: [],
    ContactStatus.LOST: [ContactStatus.IN_PROGRESS],
    ContactStatus.NOT_INTERESTED: [ContactStatus.IN_PROGRESS],
    ContactStatus.DO_NOT_CONTACT: [],  # Terminal — no transitions
    ContactStatus.DUPLICATE: [],
}


class ContactService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)

    def _can_view_contact(self, contact: Contact, user: User) -> bool:
        """Service-layer authorization check."""
        if user.is_manager_or_above:
            return True
        if user.is_team_leader_or_above and contact.team_id and str(contact.team_id) == str(user.team_id):
            return True
        if contact.owner_id and str(contact.owner_id) == str(user.id):
            return True
        return False

    async def list_contacts(
        self,
        user: User,
        page: int = 1,
        per_page: int = 25,
        search: Optional[str] = None,
        status: Optional[str] = None,
        owner_id: Optional[str] = None,
        team_id: Optional[str] = None,
        company_id: Optional[str] = None,
        country: Optional[str] = None,
        industry: Optional[str] = None,
        position: Optional[str] = None,
        last_outcome: Optional[str] = None,
        final_outcome: Optional[str] = None,
        attempt_count: Optional[int] = None,
        campaign_id: Optional[str] = None,
        is_dnc: Optional[bool] = None,
        priority: Optional[str] = None,
        source_sheet: Optional[str] = None,
        sort_by: str = "sheet_order",
        sort_dir: str = "asc",
        include_archived: bool = False,
        archived_only: bool = False,
        pending_claim_only: bool = False,
    ) -> Tuple[List[Contact], int]:
        stmt = select(Contact).where(Contact.deleted_at.is_(None))
        stmt = stmt.options(
            selectinload(Contact.owner),
            selectinload(Contact.company),
            selectinload(Contact.archived_by),
            selectinload(Contact.calls),
        )

        # Row-level security — scope visible contacts by role
        if not user.is_manager_or_above and not user.is_data_ops:
            if user.is_team_leader_or_above:
                stmt = stmt.where(
                    or_(Contact.owner_id == user.id, Contact.team_id == user.team_id)
                )
            else:
                stmt = stmt.where(Contact.owner_id == user.id)

        # Filters
        if search:
            q = f"%{search}%"
            stmt = stmt.outerjoin(Contact.company).where(
                or_(
                    Contact.first_name.ilike(q),
                    Contact.last_name.ilike(q),
                    Contact.email.ilike(q),
                    Contact.phone.ilike(q),
                    Contact.position.ilike(q),
                    Contact.final_outcome.ilike(q),
                    Company.name.ilike(q),
                )
            )
        if status and status != "ARCHIVED":
            if status in ["EMAIL_AND_WHATSAPP", "EMAIL_OR_WHATSAPP", "EMAIL_WHATSAPP"]:
                stmt = stmt.where(
                    or_(
                        Contact.status.in_([ContactStatus.EMAIL_REQUESTED, ContactStatus.WHATSAPP_REQUESTED]),
                        Contact.last_outcome.ilike("%email%"),
                        Contact.last_outcome.ilike("%whata%"),
                        Contact.last_outcome.ilike("%whatsapp%"),
                    )
                )
            else:
                stmt = stmt.where(Contact.status == status)
        if final_outcome:
            stmt = stmt.where(Contact.final_outcome.ilike(f"%{final_outcome}%"))
        if owner_id:
            if owner_id == "unassigned":
                stmt = stmt.where(Contact.owner_id.is_(None))
            else:
                stmt = stmt.where(Contact.owner_id == uuid.UUID(owner_id))
        if team_id:
            stmt = stmt.where(Contact.team_id == uuid.UUID(team_id))
        if company_id:
            stmt = stmt.where(Contact.company_id == uuid.UUID(company_id))
        if country:
            stmt = stmt.where(Contact.country.ilike(f"%{country}%"))
        if industry:
            stmt = stmt.where(Contact.industry.ilike(f"%{industry}%"))
        if position:
            stmt = stmt.where(Contact.position.ilike(f"%{position}%"))
        if last_outcome:
            stmt = stmt.where(Contact.last_outcome == last_outcome)
        if attempt_count is not None:
            stmt = stmt.where(Contact.attempt_count == attempt_count)
        if campaign_id:
            stmt = stmt.where(Contact.campaign_id == uuid.UUID(campaign_id))
        if is_dnc is not None:
            stmt = stmt.where(Contact.is_dnc == is_dnc)
        if priority:
            stmt = stmt.where(Contact.priority == priority)
        if source_sheet:
            stmt = stmt.where(Contact.source_sheet.ilike(f"%{source_sheet}%"))

        # Archive & Pending Claim isolation
        if pending_claim_only:
            stmt = stmt.where(Contact.status == ContactStatus.PENDING_CLAIM)
        elif archived_only or status == "ARCHIVED" or status == ContactStatus.ARCHIVED:
            stmt = stmt.where(
                or_(Contact.status == ContactStatus.ARCHIVED, Contact.archived_at.is_not(None))
            )
        elif not include_archived:
            # Active contacts: strictly exclude ARCHIVED and PENDING_CLAIM
            stmt = stmt.where(
                Contact.status.not_in([ContactStatus.ARCHIVED, ContactStatus.PENDING_CLAIM]),
                Contact.archived_at.is_(None),
            )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar_one()

        # Sorting — whitelist allowed fields
        if sort_by in ["owner_first", "owner", "owner_id"]:
            if sort_dir == "desc":
                stmt = stmt.order_by(Contact.owner_id.desc().nullslast(), Contact.first_name.asc())
            else:
                stmt = stmt.order_by(Contact.owner_id.asc().nullslast(), Contact.first_name.asc())
        elif sort_by == "name":
            stmt = stmt.order_by(Contact.first_name.asc() if sort_dir == "asc" else Contact.first_name.desc())
        elif sort_by == "sheet_order":
            # Default sort: preserves original xlsx row order.
            # Contacts with sheet_order=NULL (freshly created without import) go last.
            if sort_dir == "desc":
                stmt = stmt.order_by(Contact.sheet_order.desc().nullslast())
            else:
                stmt = stmt.order_by(Contact.sheet_order.asc().nullslast())
        else:
            allowed_sort = {"created_at", "updated_at", "first_name", "last_name", "status", "priority", "last_contact_at", "attempt_count"}
            if sort_by not in allowed_sort:
                sort_by = "sheet_order"  # fall back to sheet order, not created_at
            if sort_by == "sheet_order":
                stmt = stmt.order_by(Contact.sheet_order.asc().nullslast())
            else:
                col = getattr(Contact, sort_by)
                stmt = stmt.order_by(col.desc() if sort_dir == "desc" else col.asc())

        stmt = stmt.offset((page - 1) * per_page).limit(per_page)

        result = await self.db.execute(stmt)
        return result.scalars().all(), total

    async def get_contact(self, contact_id: uuid.UUID, user: User) -> Contact:
        stmt = (
            select(Contact)
            .where(Contact.id == contact_id, Contact.deleted_at.is_(None))
            .options(
                selectinload(Contact.owner),
                selectinload(Contact.company),
                selectinload(Contact.campaign),
                selectinload(Contact.archived_by),
                selectinload(Contact.calls),
            )
        )
        result = await self.db.execute(stmt)
        contact = result.scalar_one_or_none()
        if not contact:
            raise NotFoundError("Contact not found.")
        if not self._can_view_contact(contact, user):
            raise ForbiddenError("You do not have permission to view this contact.")
        return contact

    async def create_contact(self, data: dict, actor: User, import_key: Optional[str] = None) -> Contact:
        norm_email = normalize_email(data.get("email", "") or "") or None
        norm_phone = normalize_phone(data.get("phone", "") or "") or None

        # Duplicate detection
        duplicate = await self._find_duplicate(norm_email, norm_phone)

        assigned_owner_id = uuid.UUID(data["owner_id"]) if data.get("owner_id") else (actor.id if not actor.is_manager_or_above else None)
        assigned_team_id = uuid.UUID(data["team_id"]) if data.get("team_id") else (actor.team_id if not actor.is_manager_or_above else None)

        # Auto-assign next sheet_order so manually created contacts appear at the
        # end of the list (same behaviour as appending a row to the sheet)
        max_order_result = await self.db.execute(
            select(func.coalesce(func.max(Contact.sheet_order), 0))
        )
        next_order = (max_order_result.scalar_one() or 0) + 1

        contact = Contact(
            first_name=data["first_name"],
            last_name=data.get("last_name"),
            company_id=uuid.UUID(data["company_id"]) if data.get("company_id") else None,
            position=data.get("position"),
            department=data.get("department"),
            email=data.get("email"),
            normalized_email=norm_email,
            phone=data.get("phone"),
            normalized_phone=norm_phone,
            secondary_email=data.get("secondary_email"),
            secondary_phone=data.get("secondary_phone"),
            country=data.get("country"),
            industry=data.get("industry"),
            source=data.get("source"),
            tags=data.get("tags"),
            notes=data.get("notes"),
            owner_id=assigned_owner_id,
            team_id=assigned_team_id,
            campaign_id=uuid.UUID(data["campaign_id"]) if data.get("campaign_id") else None,
            status=data.get("status", ContactStatus.NEW),
            priority=data.get("priority", ContactPriority.MEDIUM),
            import_key=import_key,
            potential_duplicate_of_id=duplicate.id if duplicate else None,
            sheet_order=next_order,
        )

        if duplicate:
            contact.status = "DUPLICATE"
            logger.warning("contact.duplicate_detected", email=norm_email, phone=norm_phone, duplicate_id=str(duplicate.id))

        self.db.add(contact)
        await self.db.flush()

        await self.audit.log(
            action="contact.created",
            entity_type="contact",
            actor_id=actor.id,
            entity_id=contact.id,
            new_value={"name": contact.full_name, "email": contact.email, "status": contact.status},
        )
        return contact

    async def update_contact(self, contact_id: uuid.UUID, data: dict, actor: User) -> Contact:
        contact = await self.get_contact(contact_id, actor)
        old = {"status": contact.status, "owner_id": str(contact.owner_id) if contact.owner_id else None}

        updatable = [
            "first_name", "last_name", "position", "department", "email", "secondary_email",
            "phone", "secondary_phone", "country", "industry", "source", "tags", "notes",
            "priority", "next_contact_at",
        ]
        for field in updatable:
            if field in data and data[field] is not None:
                setattr(contact, field, data[field])

        if "email" in data:
            contact.normalized_email = normalize_email(data["email"]) if data["email"] else None
        if "phone" in data:
            contact.normalized_phone = normalize_phone(data["phone"]) if data["phone"] else None
        if "company_id" in data:
            contact.company_id = uuid.UUID(data["company_id"]) if data["company_id"] else None

        self.db.add(contact)
        await self.db.flush()

        await self.audit.log(
            action="contact.updated",
            entity_type="contact",
            actor_id=actor.id,
            entity_id=contact.id,
            old_value=old,
            new_value={k: data[k] for k in data if k in updatable},
        )
        return contact

    async def update_status(self, contact_id: uuid.UUID, new_status: str, actor: User) -> Contact:
        contact = await self.get_contact(contact_id, actor)
        old_status = contact.status

        # Validate transition
        allowed = ALLOWED_STATUS_TRANSITIONS.get(ContactStatus(old_status), [])
        if new_status not in [s.value for s in allowed]:
            raise ValidationError(
                f"Invalid status transition from {old_status} to {new_status}."
            )

        if new_status == ContactStatus.DO_NOT_CONTACT:
            contact.is_dnc = True
            await self.audit.log(
                action="contact.dnc_set",
                entity_type="contact",
                actor_id=actor.id,
                entity_id=contact.id,
                old_value={"is_dnc": False},
                new_value={"is_dnc": True},
            )

        contact.status = new_status
        self.db.add(contact)
        await self.db.flush()

        await self.audit.log(
            action="contact.status_changed",
            entity_type="contact",
            actor_id=actor.id,
            entity_id=contact.id,
            old_value={"status": old_status},
            new_value={"status": new_status},
        )
        return await self.get_contact(contact_id, actor)

    async def set_dnc(self, contact_id: uuid.UUID, actor: User) -> Contact:
        contact = await self.get_contact(contact_id, actor)
        if contact.is_dnc:
            raise ConflictError("Contact is already marked as Do Not Contact.")

        contact.is_dnc = True
        contact.status = ContactStatus.DO_NOT_CONTACT
        self.db.add(contact)
        await self.db.flush()

        await self.audit.log(
            action="contact.dnc_set",
            entity_type="contact",
            actor_id=actor.id,
            entity_id=contact.id,
            new_value={"is_dnc": True, "status": ContactStatus.DO_NOT_CONTACT},
        )
        return await self.get_contact(contact_id, actor)

    async def assign_contact(
        self, contact_id: uuid.UUID, new_owner_id: uuid.UUID, actor: User, reason: str = ""
    ) -> Contact:
        if not actor.is_team_leader_or_above:
            raise ForbiddenError("Only team leaders and above can assign contacts.")

        contact = await self.get_contact(contact_id, actor)
        old_owner = contact.owner_id

        contact.owner_id = new_owner_id
        if contact.status == ContactStatus.UNASSIGNED:
            contact.status = ContactStatus.NEW
        self.db.add(contact)

        # Record assignment history
        from app.models.integrations import LeadAssignment
        assignment = LeadAssignment(
            contact_id=contact.id,
            assigned_to=new_owner_id,
            assigned_by=actor.id,
            previous_owner_id=old_owner,
            reason=reason,
        )
        self.db.add(assignment)
        await self.db.flush()

        await self.audit.log(
            action="contact.assigned",
            entity_type="contact",
            actor_id=actor.id,
            entity_id=contact.id,
            old_value={"owner_id": str(old_owner) if old_owner else None},
            new_value={"owner_id": str(new_owner_id), "reason": reason},
        )
        return contact

    async def soft_delete(self, contact_id: uuid.UUID, actor: User) -> None:
        if not actor.is_manager_or_above:
            raise ForbiddenError("Only managers and above can delete contacts.")
        contact = await self.get_contact(contact_id, actor)
        contact.soft_delete()
        self.db.add(contact)
        await self.db.flush()
        await self.audit.log(
            action="contact.deleted",
            entity_type="contact",
            actor_id=actor.id,
            entity_id=contact.id,
        )

    async def set_final_outcome(
        self,
        contact_id: uuid.UUID,
        final_outcome: str,
        actor: User,
        notes: Optional[str] = None,
    ) -> Contact:
        """
        Explicitly set a final outcome for a contact and move them to Archive.
        Preserves complete attempt history, calls, notes, and activity timeline.
        """
        contact = await self.get_contact(contact_id, actor)
        now = datetime.now(timezone.utc)
        prev_status = contact.status
        prev_outcome = contact.final_outcome

        contact.final_outcome = final_outcome
        contact.status = ContactStatus.ARCHIVED
        contact.archived_at = now
        contact.archived_by_id = actor.id

        if final_outcome in ["DO_NOT_CONTACT", "DNC"]:
            contact.is_dnc = True

        if notes:
            note_entry = f"[FINAL OUTCOME: {final_outcome}] {notes.strip()}"
            contact.notes = (contact.notes or "") + ("\n" if contact.notes else "") + note_entry

        self.db.add(contact)
        await self.db.flush()

        await self.audit.log(
            action="contact.final_outcome_set",
            entity_type="contact",
            actor_id=actor.id,
            entity_id=contact.id,
            old_value={"status": prev_status, "final_outcome": prev_outcome},
            new_value={"status": ContactStatus.ARCHIVED, "final_outcome": final_outcome, "archived_at": now.isoformat()},
        )
        return await self.get_contact(contact_id, actor)

    async def archive_contact(
        self,
        contact_id: uuid.UUID,
        actor: User,
        final_outcome: Optional[str] = None,
    ) -> Contact:
        """Move a contact to the Archive while strictly preserving all notes, calls, attempts, and timeline."""
        contact = await self.get_contact(contact_id, actor)
        if contact.status == ContactStatus.ARCHIVED:
            raise ConflictError("Contact is already archived.")

        now = datetime.now(timezone.utc)
        prev_status = contact.status
        contact.status = ContactStatus.ARCHIVED
        contact.archived_at = now
        contact.archived_by_id = actor.id
        if final_outcome:
            contact.final_outcome = final_outcome

        archive_note = f"[ARCHIVED] Previous status: {prev_status}"
        contact.notes = (contact.notes or "") + ("\n" if contact.notes else "") + archive_note
        self.db.add(contact)
        await self.db.flush()

        await self.audit.log(
            action="contact.archived",
            entity_type="contact",
            actor_id=actor.id,
            entity_id=contact.id,
            old_value={"status": prev_status},
            new_value={"status": ContactStatus.ARCHIVED, "archived_at": now.isoformat(), "final_outcome": contact.final_outcome},
        )
        return await self.get_contact(contact_id, actor)

    async def unarchive_contact(self, contact_id: uuid.UUID, actor: User) -> Contact:
        """Restore a contact from archive back to Active Contacts."""
        contact = await self.get_contact(contact_id, actor)
        if contact.status != ContactStatus.ARCHIVED and contact.archived_at is None:
            raise ValidationError("Contact is not archived.")

        prev_outcome = contact.final_outcome
        contact.status = ContactStatus.NEW
        contact.archived_at = None
        contact.archived_by_id = None
        contact.final_outcome = None
        self.db.add(contact)
        await self.db.flush()

        await self.audit.log(
            action="contact.unarchived",
            entity_type="contact",
            actor_id=actor.id,
            entity_id=contact.id,
            old_value={"status": ContactStatus.ARCHIVED, "final_outcome": prev_outcome},
            new_value={"status": ContactStatus.NEW},
        )
        return await self.get_contact(contact_id, actor)

    async def claim_contact(self, contact_id: uuid.UUID, actor: User) -> Contact:
        """Claim a single contact from personal pool and append to end of user's active contacts queue."""
        stmt = (
            select(Contact)
            .where(Contact.id == contact_id, Contact.deleted_at.is_(None))
            .options(selectinload(Contact.owner), selectinload(Contact.company))
        )
        result = await self.db.execute(stmt)
        contact = result.scalar_one_or_none()
        if not contact:
            raise NotFoundError("Contact not found.")

        if contact.status != ContactStatus.PENDING_CLAIM:
            raise ValidationError("Contact is not in your personal pool (not PENDING_CLAIM status).")

        if contact.owner_id != actor.id and not actor.is_manager_or_above:
            raise ForbiddenError("You can only claim contacts assigned to you.")

        # Append at the END of user's active contacts
        max_order_result = await self.db.execute(
            select(func.coalesce(func.max(Contact.sheet_order), 0))
            .where(
                Contact.owner_id == actor.id,
                Contact.deleted_at.is_(None),
                Contact.status.not_in([ContactStatus.PENDING_CLAIM, ContactStatus.ARCHIVED]),
            )
        )
        next_order = (max_order_result.scalar_one() or 0) + 1

        contact.status = ContactStatus.NEW
        contact.sheet_order = next_order
        self.db.add(contact)
        await self.db.flush()

        await self.audit.log(
            action="contact.claimed",
            entity_type="contact",
            actor_id=actor.id,
            entity_id=contact.id,
            old_value={"status": ContactStatus.PENDING_CLAIM},
            new_value={"status": ContactStatus.NEW, "sheet_order": next_order},
        )
        return await self.get_contact(contact_id, actor)

    async def claim_bulk_contacts(self, contact_ids: List[uuid.UUID], actor: User) -> List[Contact]:
        """
        Claim multiple contacts from personal pool in batch.
        CRITICAL QUEUE ORDERING RULE:
        1. All newly claimed contacts are appended AFTER existing active contacts.
        2. Within the newly claimed batch, relative sheet_order is strictly preserved.
        """
        if not contact_ids:
            return []

        stmt = (
            select(Contact)
            .where(
                Contact.id.in_(contact_ids),
                Contact.deleted_at.is_(None),
                Contact.status == ContactStatus.PENDING_CLAIM,
            )
            .options(selectinload(Contact.owner), selectinload(Contact.company))
        )
        if not actor.is_manager_or_above:
            stmt = stmt.where(Contact.owner_id == actor.id)

        contacts = list((await self.db.execute(stmt)).scalars().all())
        if not contacts:
            return []

        # Sort batch by existing sheet_order (preserving original Google Sheet order)
        contacts.sort(key=lambda c: (c.sheet_order if c.sheet_order is not None else 999999999, c.created_at or datetime.min))

        # Find current highest sheet_order in active contacts
        max_order_result = await self.db.execute(
            select(func.coalesce(func.max(Contact.sheet_order), 0))
            .where(
                Contact.owner_id == actor.id,
                Contact.deleted_at.is_(None),
                Contact.status.not_in([ContactStatus.PENDING_CLAIM, ContactStatus.ARCHIVED]),
            )
        )
        curr_order = max_order_result.scalar_one() or 0

        claimed = []
        for c in contacts:
            curr_order += 1
            c.status = ContactStatus.NEW
            c.sheet_order = curr_order
            self.db.add(c)
            claimed.append(c)

        await self.db.flush()

        for c in claimed:
            await self.audit.log(
                action="contact.claimed",
                entity_type="contact",
                actor_id=actor.id,
                entity_id=c.id,
                old_value={"status": ContactStatus.PENDING_CLAIM},
                new_value={"status": ContactStatus.NEW, "sheet_order": c.sheet_order},
            )

        return claimed

    async def get_timeline(self, contact_id: uuid.UUID, user: User, page: int = 1, per_page: int = 25):
        """Unified chronological timeline of all activities for a contact."""
        contact = await self.get_contact(contact_id, user)

        from app.models.call import Call
        from app.models.note import Note
        from app.models.task import Task
        from app.models.activity import EmailActivity, WhatsAppActivity
        from app.models.audit import AuditLog

        # Collect timeline items from all sources
        items = []

        # Calls
        calls = (await self.db.execute(
            select(Call).where(Call.contact_id == contact_id).options(selectinload(Call.user)).order_by(Call.called_at.desc())
        )).scalars().all()
        for c in calls:
            items.append({
                "type": "call", "id": str(c.id), "timestamp": c.called_at.isoformat(),
                "user": c.user.full_name if c.user else "Unknown",
                "outcome": c.outcome, "notes": c.notes, "duration_seconds": c.duration_seconds,
            })

        # Notes
        notes = (await self.db.execute(
            select(ContactNote).where(ContactNote.contact_id == contact_id).options(selectinload(ContactNote.user)).order_by(ContactNote.created_at.desc())
        )).scalars().all()
        for n in notes:
            items.append({
                "type": "note", "id": str(n.id), "timestamp": n.created_at.isoformat(),
                "user": n.user.full_name if n.user else "Unknown",
                "notes": n.note_text, "content": n.note_text, "is_pinned": n.is_pinned,
            })

        # Tasks
        tasks = (await self.db.execute(
            select(Task).where(Task.contact_id == contact_id).options(selectinload(Task.assignee)).order_by(Task.created_at.desc())
        )).scalars().all()
        for t in tasks:
            items.append({
                "type": "task", "id": str(t.id), "timestamp": t.created_at.isoformat(),
                "user": t.assignee.full_name if t.assignee else "Unknown",
                "task_type": t.type, "status": t.status, "title": t.title,
                "due_at": t.due_at.isoformat() if t.due_at else None,
            })

        # Email activities
        emails = (await self.db.execute(
            select(EmailActivity).where(EmailActivity.contact_id == contact_id).options(selectinload(EmailActivity.sender))
        )).scalars().all()
        for e in emails:
            items.append({
                "type": "email", "id": str(e.id), "timestamp": e.sent_at.isoformat(),
                "user": e.sender.full_name if e.sender else "Unknown",
                "subject": e.subject, "direction": e.direction,
            })

        # WhatsApp
        whatsapps = (await self.db.execute(
            select(WhatsAppActivity).where(WhatsAppActivity.contact_id == contact_id).options(selectinload(WhatsAppActivity.sender))
        )).scalars().all()
        for w in whatsapps:
            items.append({
                "type": "whatsapp", "id": str(w.id), "timestamp": w.sent_at.isoformat(),
                "user": w.sender.full_name if w.sender else "Unknown",
                "message_preview": w.message_preview, "direction": w.direction,
            })

        # Status changes from audit log
        status_changes = (await self.db.execute(
            select(AuditLog)
            .where(AuditLog.entity_type == "contact", AuditLog.entity_id == contact_id,
                   AuditLog.action == "contact.status_changed")
            .options(selectinload(AuditLog.actor))
            .order_by(AuditLog.created_at.desc())
        )).scalars().all()
        for a in status_changes:
            items.append({
                "type": "status_change", "id": str(a.id), "timestamp": a.created_at.isoformat(),
                "user": a.actor.full_name if a.actor else "System",
                "old_status": a.old_value.get("status") if a.old_value else None,
                "new_status": a.new_value.get("status") if a.new_value else None,
            })

        # Sort all items by timestamp descending
        items.sort(key=lambda x: x["timestamp"], reverse=True)

        # Paginate
        total = len(items)
        start = (page - 1) * per_page
        end = start + per_page
        return items[start:end], total

    async def _find_duplicate(
        self, normalized_email: Optional[str], normalized_phone: Optional[str]
    ) -> Optional[Contact]:
        """Check for exact email or phone duplicates."""
        conditions = []
        if normalized_email:
            conditions.append(Contact.normalized_email == normalized_email)
        if normalized_phone and len(normalized_phone) >= 7:
            conditions.append(Contact.normalized_phone == normalized_phone)

        if not conditions:
            return None

        stmt = select(Contact).where(
            or_(*conditions),
            Contact.deleted_at.is_(None),
            Contact.status != ContactStatus.DUPLICATE,
        ).limit(1)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def record_quick_call(
        self,
        contact_id: uuid.UUID,
        outcome: str,
        notes: Optional[str] = None,
        duration_seconds: Optional[int] = 0,
        callback_requested_at: Optional[datetime] = None,
        actor: Optional[User] = None,
    ) -> Tuple[Contact, Any]:
        from datetime import timedelta
        from app.models.call import Call
        from app.models.recall import Recall
        from app.models.no_answer import NoAnswerQueue
        from app.automation.service import AutomationService

        contact = await self.get_contact(contact_id, actor)
        if contact.is_dnc:
            raise DNCError()

        now = datetime.now(timezone.utc)
        contact.attempt_count = (contact.attempt_count or 0) + 1
        contact.last_outcome = outcome
        contact.last_contact_at = now
        if notes:
            contact.notes = notes

        # Outcome normalization
        norm_outcome = outcome.strip()
        upper_out = norm_outcome.upper().replace(" ", "_")

        if "NO_ANSWER" in upper_out or upper_out == "NA":
            contact.status = ContactStatus.NO_ANSWER
            # Schedule 48h retry if attempt count <= 5
            if contact.attempt_count <= 5:
                retry_time = now + timedelta(hours=48)
                na_stmt = select(NoAnswerQueue).where(
                    NoAnswerQueue.contact_id == contact.id,
                    NoAnswerQueue.status == "PENDING",
                )
                existing_na = (await self.db.execute(na_stmt)).scalar_one_or_none()
                if existing_na:
                    existing_na.attempt_number = contact.attempt_count
                    existing_na.last_attempt_at = now
                    existing_na.next_attempt_at = retry_time
                    self.db.add(existing_na)
                else:
                    new_na = NoAnswerQueue(
                        contact_id=contact.id,
                        user_id=contact.owner_id or (actor.id if actor else None),
                        attempt_number=contact.attempt_count,
                        last_attempt_at=now,
                        next_attempt_at=retry_time,
                        status="PENDING",
                    )
                    self.db.add(new_na)
        else:
            # If outcome is answered / other, resolve any pending no-answer queue entry
            na_stmt = select(NoAnswerQueue).where(
                NoAnswerQueue.contact_id == contact.id,
                NoAnswerQueue.status == "PENDING",
            )
            existing_na_list = (await self.db.execute(na_stmt)).scalars().all()
            for na_item in existing_na_list:
                await self.db.delete(na_item)

        if "EMAIL" in upper_out:
            contact.status = ContactStatus.EMAIL_REQUESTED
        elif "WHATSAPP" in upper_out or "WHATA" in upper_out:
            contact.status = ContactStatus.WHATSAPP_REQUESTED
        elif "DEMO" in upper_out:
            contact.status = ContactStatus.DEMO_SCHEDULED
        elif "RE_CALL" in upper_out or "RECALL" in upper_out or "CALL_LATER" in upper_out or callback_requested_at:
            contact.status = ContactStatus.RECALL_SCHEDULED
        elif "INTERESTED" in upper_out and "NOT" not in upper_out:
            contact.status = ContactStatus.INTERESTED
        elif "NOT_INTERESTED" in upper_out:
            contact.status = ContactStatus.NOT_INTERESTED
        elif "DO_NOT_CONTACT" in upper_out or "DNC" in upper_out:
            contact.is_dnc = True
            contact.status = ContactStatus.DO_NOT_CONTACT

        # Complete any existing pending recall for this contact since a new call was made
        existing_recalls = (
            await self.db.execute(
                select(Recall).where(Recall.contact_id == contact.id, Recall.status == "PENDING")
            )
        ).scalars().all()
        for r in existing_recalls:
            r.status = "COMPLETED"
            r.completed_at = now
            self.db.add(r)

        # If a recall was scheduled with this call
        if callback_requested_at or "RE_CALL" in upper_out or "RECALL" in upper_out or "CALL_LATER" in upper_out:
            sched_at = callback_requested_at or (now + timedelta(days=1))
            new_recall = Recall(
                contact_id=contact.id,
                user_id=contact.owner_id or (actor.id if actor else None),
                scheduled_at=sched_at,
                notes=notes,
                status="PENDING",
            )
            self.db.add(new_recall)

        call = Call(
            contact_id=contact.id,
            user_id=actor.id if actor else None,
            outcome=outcome,
            attempt_number=contact.attempt_count,
            duration_seconds=duration_seconds or 0,
            notes=notes,
            called_at=now,
            callback_requested_at=callback_requested_at,
        )
        self.db.add(call)
        self.db.add(contact)
        await self.db.flush()

        # Fire automation engine
        automation_svc = AutomationService(self.db)
        await automation_svc.fire_event(
            event=f"call.outcome.{outcome.lower()}",
            entity_id=contact.id,
            entity_type="contact",
            payload={
                "call_id": str(call.id),
                "contact_id": str(contact.id),
                "owner_id": str(contact.owner_id) if contact.owner_id else (str(actor.id) if actor else None),
                "outcome": outcome,
                "notes": notes,
                "callback_requested_at": callback_requested_at.isoformat() if callback_requested_at else None,
                "user_id": str(actor.id) if actor else None,
            },
            actor_id=actor.id if actor else None,
        )

        # Eagerly reload contact with relationships to avoid MissingGreenlet
        target_id = contact.id
        reload_stmt = (
            select(Contact)
            .where(Contact.id == target_id)
            .options(
                selectinload(Contact.company),
                selectinload(Contact.owner),
                selectinload(Contact.calls),
            )
            .execution_options(populate_existing=True)
        )
        loaded_contact = (await self.db.execute(reload_stmt)).scalar_one()
        return loaded_contact, call

    async def correct_latest_call(
        self,
        contact_id: uuid.UUID,
        new_outcome: str,
        reason: Optional[str],
        actor: User,
    ) -> Tuple[Contact, Call]:
        """
        Safely correct the latest call outcome on a contact.
        - Verifies permission: Sales User can only correct their own latest interaction.
        - Preserves audit history.
        - Automatically rolls back obsolete consequences (e.g. cancels No Answer retry queue / tasks).
        - Executes automation for the new outcome.
        """
        contact = await self.get_contact(contact_id, actor)

        # Find the latest call on this contact
        stmt = (
            select(Call)
            .where(Call.contact_id == contact_id)
            .order_by(Call.called_at.desc())
            .limit(1)
        )
        latest_call = (await self.db.execute(stmt)).scalar_one_or_none()
        if not latest_call:
            raise ValidationError("No previous call interaction found on this contact to correct.")

        # Permission check: normal sales users can only correct their own call
        if not actor.is_manager_or_above and latest_call.user_id != actor.id:
            raise ForbiddenError("You can only correct call outcomes logged by yourself.")

        old_outcome = latest_call.outcome
        now = datetime.now(timezone.utc)

        # 1. Rollback old consequence if NO_ANSWER
        if old_outcome == "NO_ANSWER":
            no_ans_stmt = select(NoAnswerQueue).where(NoAnswerQueue.contact_id == contact_id)
            no_ans_entries = (await self.db.execute(no_ans_stmt)).scalars().all()
            for na in no_ans_entries:
                await self.db.delete(na)

        # 2. Update Call record with audit tracking
        latest_call.is_corrected = True
        latest_call.previous_outcome = old_outcome
        latest_call.outcome = new_outcome
        latest_call.correction_reason = reason or "User corrected latest outcome"
        latest_call.corrected_at = now
        latest_call.corrected_by_id = actor.id

        # 3. Update Contact status & last_outcome
        contact.last_outcome = new_outcome
        match new_outcome:
            case "NO_ANSWER":
                contact.status = ContactStatus.NO_ANSWER
            case "INTERESTED":
                contact.status = ContactStatus.INTERESTED
            case "EMAIL_REQUESTED":
                contact.status = ContactStatus.EMAIL_REQUESTED
            case "WHATSAPP_REQUESTED":
                contact.status = ContactStatus.WHATSAPP_REQUESTED
            case "DEMO_REQUESTED":
                contact.status = ContactStatus.DEMO_SCHEDULED
            case "CALL_LATER":
                contact.status = ContactStatus.RECALL_SCHEDULED
            case "DO_NOT_CONTACT":
                contact.is_dnc = True
                contact.status = ContactStatus.DO_NOT_CONTACT
            case "NOT_INTERESTED":
                contact.status = ContactStatus.NOT_INTERESTED

        self.db.add(latest_call)
        self.db.add(contact)
        await self.db.flush()

        # 4. Immutable Audit Log
        audit = AuditService(self.db)
        await audit.log(
            action="call.outcome_corrected",
            entity_type="contact",
            actor_id=actor.id,
            entity_id=contact.id,
            old_value={"outcome": old_outcome, "call_id": str(latest_call.id)},
            new_value={"outcome": new_outcome, "reason": reason, "call_id": str(latest_call.id)},
        )

        # 5. Fire new automation for the corrected outcome
        automation_svc = AutomationService(self.db)
        await automation_svc.fire_event(
            event=f"call.outcome.{new_outcome.lower()}",
            entity_id=contact.id,
            entity_type="contact",
            payload={
                "call_id": str(latest_call.id),
                "contact_id": str(contact.id),
                "owner_id": str(contact.owner_id) if contact.owner_id else (str(actor.id) if actor else None),
                "outcome": new_outcome,
                "notes": latest_call.notes,
                "is_corrected": True,
                "user_id": str(actor.id) if actor else None,
            },
            actor_id=actor.id,
        )

        # Eager reload
        reload_stmt = (
            select(Contact)
            .where(Contact.id == contact.id)
            .options(selectinload(Contact.company), selectinload(Contact.owner))
        )
        loaded_contact = (await self.db.execute(reload_stmt)).scalar_one()
        return loaded_contact, latest_call

    async def add_note(
        self,
        contact_id: uuid.UUID,
        note_text: str,
        actor: User,
        is_pinned: bool = False,
    ) -> ContactNote:
        """Add a timestamped note to a contact history."""
        if not note_text or not note_text.strip():
            raise ValidationError("Note text cannot be empty.")

        contact = await self.get_contact(contact_id, actor)

        note = ContactNote(
            contact_id=contact_id,
            user_id=actor.id,
            note_text=note_text.strip(),
            is_pinned=is_pinned,
        )
        contact.notes = note_text.strip()
        self.db.add(note)
        self.db.add(contact)
        await self.db.flush()

        audit = AuditService(self.db)
        await audit.log(
            action="contact.note_added",
            entity_type="contact",
            actor_id=actor.id,
            entity_id=contact.id,
            new_value={"note_id": str(note.id), "note_text": note.note_text},
        )
        return note

    async def list_notes(self, contact_id: uuid.UUID) -> List[ContactNote]:
        """List all notes for a contact in chronological order."""
        stmt = (
            select(ContactNote)
            .where(ContactNote.contact_id == contact_id, ContactNote.deleted_at.is_(None))
            .options(selectinload(ContactNote.user))
            .order_by(ContactNote.created_at.desc())
        )
        return list((await self.db.execute(stmt)).scalars().all())

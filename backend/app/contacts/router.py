"""Contacts router — full CRUD, DNC, status, assign, timeline."""
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.dependencies import get_current_user
from app.contacts.service import ContactService
from app.database import get_db
from app.models.user import User
from app.models.contact import Contact
from pydantic import BaseModel

router = APIRouter(prefix="/contacts", tags=["Contacts"])


class ContactCreateBody(BaseModel):
    first_name: str
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    secondary_email: Optional[str] = None
    secondary_phone: Optional[str] = None
    company_id: Optional[str] = None
    position: Optional[str] = None
    department: Optional[str] = None
    country: Optional[str] = None
    industry: Optional[str] = None
    source: Optional[str] = None
    tags: Optional[str] = None
    notes: Optional[str] = None
    owner_id: Optional[str] = None
    team_id: Optional[str] = None
    campaign_id: Optional[str] = None
    priority: Optional[str] = None


class ContactUpdateBody(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    secondary_email: Optional[str] = None
    secondary_phone: Optional[str] = None
    company_id: Optional[str] = None
    company_name: Optional[str] = None
    position: Optional[str] = None
    job_title: Optional[str] = None
    department: Optional[str] = None
    country: Optional[str] = None
    industry: Optional[str] = None
    source: Optional[str] = None
    tags: Optional[str] = None
    notes: Optional[str] = None
    priority: Optional[str] = None
    owner_id: Optional[str] = None
    status: Optional[str] = None


class StatusUpdateBody(BaseModel):
    status: str


class AssignBody(BaseModel):
    owner_id: str
    reason: Optional[str] = ""


class QuickCallBody(BaseModel):
    outcome: str
    notes: Optional[str] = None
    duration_seconds: Optional[int] = 0
    callback_requested_at: Optional[str] = None


class CorrectOutcomeBody(BaseModel):
    new_outcome: str
    reason: Optional[str] = None


class FinalOutcomeBody(BaseModel):
    final_outcome: str
    notes: Optional[str] = None


class ContactNoteCreateBody(BaseModel):
    note_text: str
    is_pinned: Optional[bool] = False


def _contact_to_dict(c: Contact) -> Dict[str, Any]:
    d = c.__dict__
    
    def get_val(key, default=None):
        return d.get(key, default)

    created_at = get_val("created_at")
    updated_at = get_val("updated_at")
    archived_at = get_val("archived_at")
    last_contact_at = get_val("last_contact_at")
    next_contact_at = get_val("next_contact_at")

    status = get_val("status")
    if hasattr(status, "value"):
        status = status.value
    priority = get_val("priority")
    if hasattr(priority, "value"):
        priority = priority.value

    owner_obj = get_val("owner")
    comp_obj = get_val("company")
    arch_by_obj = get_val("archived_by")

    first_name = get_val("first_name", "")
    last_name = get_val("last_name", "")
    full_name = f"{first_name or ''} {last_name or ''}".strip()

    # Construct unified attempts list
    from sqlalchemy import inspect as sa_inspect
    calls_val = None
    try:
        insp = sa_inspect(c)
        if "calls" not in insp.unloaded:
            calls_val = c.calls
    except Exception:
        calls_val = d.get("calls")

    attempts_list: List[Dict[str, Any]] = []
    if calls_val:
        sorted_calls = sorted(
            calls_val,
            key=lambda x: (
                getattr(x, "called_at", None) or getattr(x, "created_at", None) or datetime.min.replace(tzinfo=timezone.utc),
                getattr(x, "attempt_number", 0) or 0,
            )
        )
        for idx, cl in enumerate(sorted_calls):
            attempts_list.append({
                "id": str(getattr(cl, "id", "")),
                "outcome": getattr(cl, "outcome", None),
                "attempt_number": idx + 1,
                "notes": getattr(cl, "notes", None),
                "called_at": cl.called_at.isoformat() if getattr(cl, "called_at", None) else None,
            })
    else:
        # Fallback to historical sheet attempt columns if no Call records exist
        if get_val("attempt_1"):
            attempts_list.append({"outcome": get_val("attempt_1"), "attempt_number": 1})
        if get_val("attempt_2"):
            attempts_list.append({"outcome": get_val("attempt_2"), "attempt_number": 2})
        if get_val("attempt_3"):
            attempts_list.append({"outcome": get_val("attempt_3"), "attempt_number": 3})

    attempt_count = max(len(attempts_list), get_val("attempt_count") or 0)

    return {
        "id": str(get_val("id")),
        "first_name": first_name,
        "last_name": last_name,
        "full_name": full_name,
        "email": get_val("email"),
        "phone": get_val("phone"),
        "country": get_val("country"),
        "industry": get_val("industry"),
        "position": get_val("position"),
        "job_title": get_val("position"),
        "department": get_val("department"),
        "source": get_val("source"),
        "tags": get_val("tags"),
        "notes": get_val("notes"),
        "status": status,
        "priority": priority,
        "is_dnc": get_val("is_dnc", False),
        "attempt_count": attempt_count,
        "attempts": attempts_list,
        "last_outcome": get_val("last_outcome") or (attempts_list[-1]["outcome"] if attempts_list else None),
        "final_outcome": get_val("final_outcome"),
        "archived_at": archived_at.isoformat() if archived_at else None,
        "archived_by_id": str(get_val("archived_by_id")) if get_val("archived_by_id") else None,
        "archived_by_name": getattr(arch_by_obj, "full_name", None) if arch_by_obj else None,
        "attempt_1": get_val("attempt_1"),
        "attempt_2": get_val("attempt_2"),
        "attempt_3": get_val("attempt_3"),
        "source_sheet": get_val("source_sheet"),
        "sheet_order": get_val("sheet_order"),
        "owner_id": str(get_val("owner_id")) if get_val("owner_id") else None,
        "owner_name": getattr(owner_obj, "full_name", None) if owner_obj else None,
        "company_id": str(get_val("company_id")) if get_val("company_id") else None,
        "company_name": getattr(comp_obj, "name", None) if comp_obj else None,
        "campaign_id": str(get_val("campaign_id")) if get_val("campaign_id") else None,
        "potential_duplicate_of_id": str(get_val("potential_duplicate_of_id")) if get_val("potential_duplicate_of_id") else None,
        "import_key": get_val("import_key"),
        "last_contact_at": last_contact_at.isoformat() if last_contact_at else None,
        "next_contact_at": next_contact_at.isoformat() if next_contact_at else None,
        "created_at": created_at.isoformat() if created_at else None,
        "updated_at": updated_at.isoformat() if updated_at else None,
    }


@router.get("")
async def list_contacts(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=5000),
    search: Optional[str] = Query(None, max_length=200),
    status: Optional[str] = Query(None),
    owner_id: Optional[str] = Query(None),
    team_id: Optional[str] = Query(None),
    company_id: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    industry: Optional[str] = Query(None),
    position: Optional[str] = Query(None),
    last_outcome: Optional[str] = Query(None),
    final_outcome: Optional[str] = Query(None),
    attempt_count: Optional[int] = Query(None),
    campaign_id: Optional[str] = Query(None),
    is_dnc: Optional[bool] = Query(None),
    priority: Optional[str] = Query(None),
    source_sheet: Optional[str] = Query(None),
    include_archived: bool = Query(False),
    archived_only: bool = Query(False),
    pending_claim_only: bool = Query(False),
    sort_by: str = Query("sheet_order"),
    sort_dir: str = Query("asc"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ContactService(db)
    contacts, total = await service.list_contacts(
        user=current_user, page=page, per_page=per_page,
        search=search, status=status, owner_id=owner_id, team_id=team_id,
        company_id=company_id, country=country, industry=industry,
        position=position, last_outcome=last_outcome, final_outcome=final_outcome,
        attempt_count=attempt_count, campaign_id=campaign_id, is_dnc=is_dnc,
        priority=priority, source_sheet=source_sheet, sort_by=sort_by, sort_dir=sort_dir,
        include_archived=include_archived, archived_only=archived_only,
        pending_claim_only=pending_claim_only,
    )
    return {
        "data": [_contact_to_dict(c) for c in contacts],
        "meta": {"total": total, "page": page, "per_page": per_page, "total_pages": -(-total // per_page)},
    }


@router.post("", status_code=201)
async def create_contact(
    body: ContactCreateBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ContactService(db)
    contact = await service.create_contact(body.model_dump(), actor=current_user)
    return {"data": _contact_to_dict(contact)}


@router.get("/{contact_id}")
async def get_contact(
    contact_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ContactService(db)
    contact = await service.get_contact(contact_id, current_user)
    return {"data": _contact_to_dict(contact)}


@router.patch("/{contact_id}")
async def update_contact(
    contact_id: uuid.UUID,
    body: ContactUpdateBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ContactService(db)
    contact = await service.update_contact(contact_id, body.model_dump(exclude_unset=True), current_user)
    return {"data": _contact_to_dict(contact)}


@router.patch("/{contact_id}/status")
async def update_status(
    contact_id: uuid.UUID,
    body: StatusUpdateBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ContactService(db)
    contact = await service.update_status(contact_id, body.status, current_user)
    return {"data": _contact_to_dict(contact)}


@router.post("/{contact_id}/dnc")
async def set_dnc(
    contact_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ContactService(db)
    contact = await service.set_dnc(contact_id, current_user)
    return {"data": _contact_to_dict(contact)}


@router.post("/{contact_id}/assign")
async def assign_contact(
    contact_id: uuid.UUID,
    body: AssignBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ContactService(db)
    contact = await service.assign_contact(
        contact_id, uuid.UUID(body.owner_id), current_user, body.reason or ""
    )
    return {"data": _contact_to_dict(contact)}


@router.post("/{contact_id}/quick-call")
async def quick_call_contact(
    contact_id: uuid.UUID,
    body: QuickCallBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Record an inline call attempt & outcome directly from contacts table without modal/navigation."""
    from datetime import datetime
    service = ContactService(db)
    cb_at = datetime.fromisoformat(body.callback_requested_at) if body.callback_requested_at else None
    contact, call = await service.record_quick_call(
        contact_id=contact_id,
        outcome=body.outcome,
        notes=body.notes,
        duration_seconds=body.duration_seconds or 0,
        callback_requested_at=cb_at,
        actor=current_user,
    )
    return {
        "data": _contact_to_dict(contact),
        "call": {
            "id": str(call.id),
            "outcome": call.outcome,
            "attempt_number": call.attempt_number,
            "called_at": call.called_at.isoformat(),
        },
        "message": f"Recorded outcome: {body.outcome}",
    }


@router.post("/{contact_id}/correct-outcome")
async def correct_call_outcome(
    contact_id: uuid.UUID,
    body: CorrectOutcomeBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Safely correct or undo the latest logged call outcome with full audit tracking and automation rollback."""
    service = ContactService(db)
    contact, call = await service.correct_latest_call(
        contact_id=contact_id,
        new_outcome=body.new_outcome,
        reason=body.reason,
        actor=current_user,
    )
    return {
        "data": _contact_to_dict(contact),
        "call": {
            "id": str(call.id),
            "outcome": call.outcome,
            "previous_outcome": call.previous_outcome,
            "is_corrected": call.is_corrected,
            "correction_reason": call.correction_reason,
            "called_at": call.called_at.isoformat(),
        },
        "message": f"Outcome corrected to: {body.new_outcome}",
    }


@router.post("/{contact_id}/notes", status_code=201)
async def add_contact_note(
    contact_id: uuid.UUID,
    body: ContactNoteCreateBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a quick timestamped note to the contact's history."""
    service = ContactService(db)
    note = await service.add_note(
        contact_id=contact_id,
        note_text=body.note_text,
        actor=current_user,
        is_pinned=body.is_pinned or False,
    )
    return {
        "data": {
            "id": str(note.id),
            "contact_id": str(note.contact_id),
            "user_id": str(note.user_id) if note.user_id else None,
            "user_name": current_user.full_name,
            "note_text": note.note_text,
            "is_pinned": note.is_pinned,
            "created_at": note.created_at.isoformat(),
        },
        "message": "Note added successfully.",
    }


@router.get("/{contact_id}/notes")
async def list_contact_notes(
    contact_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all timestamped notes for a contact in reverse chronological order."""
    service = ContactService(db)
    notes = await service.list_notes(contact_id)
    return {
        "data": [
            {
                "id": str(n.id),
                "contact_id": str(n.contact_id),
                "user_id": str(n.user_id) if n.user_id else None,
                "user_name": n.user.full_name if n.user else "Unknown",
                "note_text": n.note_text,
                "is_pinned": n.is_pinned,
                "created_at": n.created_at.isoformat(),
            }
            for n in notes
        ]
    }


@router.get("/{contact_id}/timeline")
async def get_timeline(
    contact_id: uuid.UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ContactService(db)
    items, total = await service.get_timeline(contact_id, current_user, page, per_page)
    return {"data": items, "meta": {"total": total, "page": page, "per_page": per_page}}


@router.delete("/{contact_id}", status_code=204)
async def delete_contact(
    contact_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ContactService(db)
    await service.soft_delete(contact_id, current_user)


@router.post("/{contact_id}/final-outcome")
async def set_final_outcome(
    contact_id: uuid.UUID,
    body: FinalOutcomeBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Explicitly set a final outcome for a contact and move them to Archive."""
    service = ContactService(db)
    contact = await service.set_final_outcome(
        contact_id=contact_id,
        final_outcome=body.final_outcome,
        actor=current_user,
        notes=body.notes,
    )
    return {
        "data": _contact_to_dict(contact),
        "message": f"Final outcome set to '{body.final_outcome}' and contact moved to Archive.",
    }


@router.post("/{contact_id}/archive")
async def archive_contact(
    contact_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Move a contact to the archive. Excluded from default Contacts & Outreach Directory."""
    service = ContactService(db)
    contact = await service.archive_contact(contact_id, current_user)
    return {"data": _contact_to_dict(contact), "message": "Contact archived successfully."}


@router.post("/{contact_id}/unarchive")
async def unarchive_contact(
    contact_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Restore a contact from archive back to the NOT_INTERESTED active status."""
    service = ContactService(db)
    contact = await service.unarchive_contact(contact_id, current_user)
    return {"data": _contact_to_dict(contact), "message": "Contact restored from archive."}


@router.post("/{contact_id}/claim")
async def claim_contact(
    contact_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Claim a lead from your personal pool (PENDING_CLAIM -> NEW).
    The lead is appended at the end of your active contacts list.
    """
    service = ContactService(db)
    contact = await service.claim_contact(contact_id, current_user)
    return {"data": _contact_to_dict(contact), "message": "Contact claimed into your active contacts."}


class BulkClaimRequest(BaseModel):
    contact_ids: List[str]


@router.post("/claim-bulk")
async def claim_bulk_contacts(
    body: BulkClaimRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Claim multiple leads from your personal pool in batch."""
    service = ContactService(db)
    c_uuids = [uuid.UUID(cid) for cid in body.contact_ids]
    claimed = await service.claim_bulk_contacts(c_uuids, current_user)
    return {
        "data": [_contact_to_dict(c) for c in claimed],
        "claimed_count": len(claimed),
        "message": f"Successfully claimed {len(claimed)} contacts into your active list.",
    }

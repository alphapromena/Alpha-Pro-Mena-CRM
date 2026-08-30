"""
Admin Router — lead distribution engine, unassigned lead pool, lead capacity management.
"""
import uuid
import math
import json
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, Body, UploadFile, File, Form
from sqlalchemy import select, func, or_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from app.auth.dependencies import require_admin, require_manager_or_above, require_data_ops_or_above
from app.database import get_db
from app.models.contact import Contact, ContactStatus
from app.models.user import User, UserRole
from app.models.integrations import LeadDistributionRule, LeadAssignment
from app.audit.service import AuditService
from app.admin.file_import import FileImportService
from app.core.exceptions import ValidationError, NotFoundError

router = APIRouter(prefix="/admin", tags=["Admin Operations"])


class DistributeLeadsRequest(BaseModel):
    contact_ids: Optional[List[str]] = None
    strategy: str  # MANUAL, ROUND_ROBIN, PERCENTAGE, COUNTS, COUNTRY, INDUSTRY
    target_user_id: Optional[str] = None  # for MANUAL
    user_percentages: Optional[Dict[str, int]] = None  # user_id -> percent (e.g. {"uuid": 40, "uuid": 60})
    user_counts: Optional[Dict[str, int]] = None  # user_id -> count (e.g. {"uuid": 250, "uuid": 250})
    country_mapping: Optional[Dict[str, str]] = None   # country -> user_id
    industry_mapping: Optional[Dict[str, str]] = None  # industry -> user_id
    campaign_id: Optional[str] = None
    include_all_unassigned: bool = False
    limit: Optional[int] = None
    count: Optional[int] = None


@router.get("/leads/unassigned")
async def get_unassigned_leads_pool(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    country: Optional[str] = Query(None),
    industry: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    campaign_id: Optional[str] = Query(None),
    current_user: User = Depends(require_data_ops_or_above),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Contact)
        .where(
            Contact.deleted_at.is_(None),
            Contact.owner_id.is_(None),
            Contact.status != ContactStatus.ARCHIVED,
        )
        .options(selectinload(Contact.company))
    )

    if country:
        stmt = stmt.where(Contact.country.ilike(f"%{country}%"))
    if industry:
        stmt = stmt.where(Contact.industry.ilike(f"%{industry}%"))
    if source:
        stmt = stmt.where(Contact.source.ilike(f"%{source}%"))
    if campaign_id:
        stmt = stmt.where(Contact.campaign_id == uuid.UUID(campaign_id))

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(Contact.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    contacts = (await db.execute(stmt)).scalars().all()

    return {
        "data": [
            {
                "id": str(c.id),
                "first_name": c.first_name,
                "last_name": c.last_name,
                "full_name": c.full_name,
                "email": c.email,
                "phone": c.phone,
                "company_name": c.company.name if c.company else None,
                "country": c.country,
                "industry": c.industry,
                "source": c.source,
                "status": c.status,
                "created_at": c.created_at.isoformat(),
            }
            for c in contacts
        ],
        "meta": {"total": total, "page": page, "per_page": per_page},
    }


@router.post("/leads/distribute")
async def distribute_leads(
    req: DistributeLeadsRequest,
    current_user: User = Depends(require_data_ops_or_above),
    db: AsyncSession = Depends(get_db),
):
    """
    Distribute unassigned leads across sales users.
    CRITICAL RULE: All distributed leads enter the recipient's Personal Pool (PENDING_CLAIM)
    and are NOT added directly to active contacts. The sales rep must review & claim them.
    """
    audit = AuditService(db)

    # 1. Fetch eligible contacts
    if req.contact_ids:
        c_stmt = select(Contact).where(
            Contact.id.in_([uuid.UUID(cid) for cid in req.contact_ids]),
            Contact.deleted_at.is_(None)
        )
    else:
        c_stmt = select(Contact).where(
            Contact.deleted_at.is_(None),
            Contact.owner_id.is_(None),
            Contact.status != ContactStatus.ARCHIVED,
        )
        if req.campaign_id:
            c_stmt = c_stmt.where(Contact.campaign_id == uuid.UUID(req.campaign_id))
        effective_limit = req.limit or req.count
        if effective_limit:
            c_stmt = c_stmt.limit(effective_limit)

    contacts = (await db.execute(c_stmt)).scalars().all()
    if not contacts:
        return {"message": "No eligible leads found for distribution.", "assigned_count": 0}

    # 2. Get active sales users and check capacity
    users_stmt = select(User).where(
        User.is_active.is_(True),
        User.deleted_at.is_(None),
        User.role.in_([UserRole.USER, "USER", "SALES_USER", UserRole.MANAGER]),
    )
    active_sales_users = (await db.execute(users_stmt)).scalars().all()
    if not active_sales_users and req.strategy != "MANUAL":
        raise ValidationError("No active sales users available for distribution.")

    assigned_count = 0
    strategy = req.strategy.upper()

    # Helper: direct SQL UPDATE for a contact (bypasses ORM version tracking)
    async def assign_contact_sql(contact_id, target_uid, old_owner_id, reason_str):
        import datetime as _dt
        await db.execute(
            update(Contact)
            .where(Contact.id == contact_id)
            .values(
                owner_id=target_uid,
                status="PENDING_CLAIM",  # Use string literal — aiosqlite doesn't auto-serialize Enums
                updated_at=_dt.datetime.now(_dt.timezone.utc),
            )
            .execution_options(synchronize_session=False)
        )
        db.add(LeadAssignment(
            contact_id=contact_id, assigned_to=target_uid, assigned_by=current_user.id,
            previous_owner_id=old_owner_id, reason=reason_str
        ))

    if strategy == "MANUAL":
        if not req.target_user_id:
            raise ValidationError("Target user ID is required for manual assignment.")
        target_uid = uuid.UUID(req.target_user_id)
        effective_limit = req.limit or req.count
        count_limit = effective_limit or len(contacts)
        for contact in contacts[:count_limit]:
            await assign_contact_sql(contact.id, target_uid, contact.owner_id,
                                     "Personal pool — awaiting claim by recipient")
            assigned_count += 1

    elif strategy in ("COUNTS", "MANUAL_COUNTS"):
        if not req.user_counts:
            raise ValidationError("user_counts mapping is required.")
        curr_idx = 0
        total_contacts = len(contacts)
        for uid_str, count_target in req.user_counts.items():
            target_uid = uuid.UUID(uid_str)
            for _ in range(count_target):
                if curr_idx >= total_contacts:
                    break
                contact = contacts[curr_idx]
                await assign_contact_sql(contact.id, target_uid, contact.owner_id,
                                         f"Bulk quota distribution ({count_target} leads)")
                curr_idx += 1
                assigned_count += 1

    elif strategy == "ROUND_ROBIN":
        user_ids = [u.id for u in active_sales_users]
        num_users = len(user_ids)
        for idx, contact in enumerate(contacts):
            target_uid = user_ids[idx % num_users]
            await assign_contact_sql(contact.id, target_uid, contact.owner_id,
                                     "Round-robin distribution to personal pool")
            assigned_count += 1

    elif strategy == "PERCENTAGE":
        if not req.user_percentages:
            raise ValidationError("user_percentages mapping is required.")
        user_buckets = [(uuid.UUID(uid_str), pct) for uid_str, pct in req.user_percentages.items()]
        total_pct = sum(pct for _, pct in user_buckets)
        if total_pct == 0:
            raise ValidationError("Total percentage must be greater than zero.")
        curr_idx = 0
        total_contacts = len(contacts)
        for target_uid, pct in user_buckets:
            quota = math.ceil((pct / total_pct) * total_contacts)
            for _ in range(quota):
                if curr_idx >= total_contacts:
                    break
                contact = contacts[curr_idx]
                await assign_contact_sql(contact.id, target_uid, contact.owner_id,
                                         f"Percentage distribution ({pct}%) to personal pool")
                curr_idx += 1
                assigned_count += 1

    elif strategy == "COUNTRY":
        if not req.country_mapping:
            raise ValidationError("country_mapping is required.")
        c_map = {k.strip().lower(): uuid.UUID(v) for k, v in req.country_mapping.items()}
        for contact in contacts:
            ct_country = (contact.country or "").strip().lower()
            if ct_country in c_map:
                target_uid = c_map[ct_country]
                await assign_contact_sql(contact.id, target_uid, contact.owner_id,
                                         f"Country distribution ({contact.country}) to personal pool")
                assigned_count += 1

    elif strategy == "INDUSTRY":
        if not req.industry_mapping:
            raise ValidationError("industry_mapping is required.")
        i_map = {k.strip().lower(): uuid.UUID(v) for k, v in req.industry_mapping.items()}
        for contact in contacts:
            ct_industry = (contact.industry or "").strip().lower()
            if ct_industry in i_map:
                target_uid = i_map[ct_industry]
                await assign_contact_sql(contact.id, target_uid, contact.owner_id,
                                         f"Industry distribution ({contact.industry}) to personal pool")
                assigned_count += 1
    else:
        raise ValidationError(f"Unknown distribution strategy: {strategy}")

    await db.flush()
    await audit.log(
        action="lead.bulk_distribution",
        entity_type="lead_distribution",
        actor_id=current_user.id,
        new_value={"strategy": strategy, "assigned_count": assigned_count, "destination": "personal_pool"},
    )

    return {
        "message": f"Successfully distributed {assigned_count} leads to personal pools using {strategy} strategy.",
        "assigned_count": assigned_count,
        "strategy": strategy,
    }


@router.get("/distribution-status")
async def get_distribution_status(
    current_user: User = Depends(require_data_ops_or_above),
    db: AsyncSession = Depends(get_db),
):
    """
    Operational Distribution Status for Aseel / Management:
    Shows assigned, claimed (active contacts), and waiting (personal pool) counts per sales rep.
    Does NOT expose sensitive sales pipeline or financial performance.
    """
    # 1. Unassigned count
    unassigned_count = (await db.execute(
        select(func.count(Contact.id)).where(
            Contact.deleted_at.is_(None),
            Contact.owner_id.is_(None),
            Contact.status != ContactStatus.ARCHIVED,
        )
    )).scalar_one() or 0

    # 2. Total in CRM
    total_crm_leads = (await db.execute(
        select(func.count(Contact.id)).where(Contact.deleted_at.is_(None))
    )).scalar_one() or 0

    # 3. Active sales users
    users_stmt = (
        select(User)
        .where(
            User.is_active.is_(True),
            User.deleted_at.is_(None),
            User.role.in_([UserRole.USER, "USER", "SALES_USER"]),
        )
        .order_by(User.first_name.asc())
    )
    sales_users = (await db.execute(users_stmt)).scalars().all()

    user_stats = []
    for u in sales_users:
        # Waiting in Personal Pool (PENDING_CLAIM)
        waiting_count = (await db.execute(
            select(func.count(Contact.id)).where(
                Contact.deleted_at.is_(None),
                Contact.owner_id == u.id,
                Contact.status == ContactStatus.PENDING_CLAIM,
            )
        )).scalar_one() or 0

        # Claimed / Active Contacts (not pending claim, not archived)
        claimed_count = (await db.execute(
            select(func.count(Contact.id)).where(
                Contact.deleted_at.is_(None),
                Contact.owner_id == u.id,
                Contact.status.not_in([ContactStatus.PENDING_CLAIM, ContactStatus.ARCHIVED]),
            )
        )).scalar_one() or 0

        # Archived Contacts
        archived_count = (await db.execute(
            select(func.count(Contact.id)).where(
                Contact.deleted_at.is_(None),
                Contact.owner_id == u.id,
                Contact.status == ContactStatus.ARCHIVED,
            )
        )).scalar_one() or 0

        total_assigned = waiting_count + claimed_count + archived_count
        claim_rate = round((claimed_count / total_assigned) * 100, 1) if total_assigned > 0 else 0.0

        user_stats.append({
            "user_id": str(u.id),
            "first_name": u.first_name,  # First name only
            "email": u.email,
            "lead_capacity": u.lead_capacity,
            "total_assigned": total_assigned,
            "claimed_count": claimed_count,
            "waiting_count": waiting_count,
            "archived_count": archived_count,
            "claim_rate": claim_rate,
        })

    # 4. Recent lead assignments log
    recent_assignments_stmt = (
        select(LeadAssignment)
        .options(selectinload(LeadAssignment.contact))
        .order_by(LeadAssignment.created_at.desc())
        .limit(20)
    )
    assignments = (await db.execute(recent_assignments_stmt)).scalars().all()

    # Pre-fetch users for assignee/assigner names
    all_users_stmt = select(User)
    all_users_map = {u.id: u.first_name for u in (await db.execute(all_users_stmt)).scalars().all()}

    assignment_logs = [
        {
            "id": str(a.id),
            "contact_name": a.contact.full_name if a.contact else "Unknown Lead",
            "assigned_to_name": all_users_map.get(a.assigned_to, "Unknown User"),
            "assigned_by_name": all_users_map.get(a.assigned_by, "System"),
            "reason": a.reason,
            "created_at": a.created_at.isoformat(),
        }
        for a in assignments
    ]

    return {
        "data": {
            "summary": {
                "total_crm_leads": total_crm_leads,
                "unassigned_leads": unassigned_count,
                "total_sales_reps": len(sales_users),
            },
            "sales_users": user_stats,
            "recent_assignments": assignment_logs,
        }
    }


@router.get("/rules/distribution")
async def list_distribution_rules(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(LeadDistributionRule).order_by(LeadDistributionRule.created_at.desc())
    rules = (await db.execute(stmt)).scalars().all()
    return {
        "data": [
            {
                "id": str(r.id),
                "name": r.name,
                "type": r.type,
                "config": r.config,
                "is_active": r.is_active,
                "created_at": r.created_at.isoformat(),
            }
            for r in rules
        ]
    }


@router.post("/rules/distribution", status_code=201)
async def create_distribution_rule(
    body: dict,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    rule = LeadDistributionRule(
        name=body["name"],
        type=body["type"],
        config=body.get("config", {}),
        campaign_id=uuid.UUID(body["campaign_id"]) if body.get("campaign_id") else None,
        is_active=body.get("is_active", True),
    )
    db.add(rule)
    await db.flush()
    return {"data": {"id": str(rule.id), "name": rule.name, "type": rule.type}}


# In-Memory / Configurable CRM System Settings State
CRM_SYSTEM_CONFIG = {
    "call_outcomes": [
        {"id": "INTERESTED", "label_en": "Interested", "label_ar": "مهتم", "color": "#10b981", "is_positive": True},
        {"id": "EMAIL_REQUESTED", "label_en": "Email Requested", "label_ar": "طلب إيميل", "color": "#0ea5e9", "is_positive": True},
        {"id": "WHATSAPP_REQUESTED", "label_en": "WhatsApp Requested", "label_ar": "طلب واتساب", "color": "#22c55e", "is_positive": True},
        {"id": "DEMO_REQUESTED", "label_en": "Demo Requested", "label_ar": "طلب عرض تجريبي", "color": "#8b5cf6", "is_positive": True},
        {"id": "CALL_LATER", "label_en": "Call Later / Callback", "label_ar": "الاتصال لاحقاً", "color": "#f59e0b", "is_positive": False},
        {"id": "NOT_INTERESTED", "label_en": "Not Interested", "label_ar": "غير مهتم", "color": "#ef4444", "is_positive": False},
        {"id": "NO_ANSWER", "label_en": "No Answer", "label_ar": "لا رد", "color": "#64748b", "is_positive": False},
        {"id": "WRONG_NUMBER", "label_en": "Wrong Number", "label_ar": "رقم خاطئ", "color": "#94a3b8", "is_positive": False},
    ],
    "no_answer_retry_hours": 48,
    "max_no_answer_attempts": 5,
    "email_followup_delay_hours": 24,
    "whatsapp_followup_delay_hours": 24,
    "default_lead_capacity": 500,
    "default_theme": "black_beige",
    "default_language": "ar",
    "primary_team_lead": "Qusai",
    "auto_assignment_enabled": True,
}


@router.get("/settings")
async def get_system_settings(
    current_user: User = Depends(require_manager_or_above),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve CRM system configuration parameters."""
    return {"data": CRM_SYSTEM_CONFIG}


@router.patch("/settings")
async def update_system_settings(
    body: dict = Body(...),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update CRM system configuration parameters (Team Lead only)."""
    audit = AuditService(db)
    old_val = {k: CRM_SYSTEM_CONFIG.get(k) for k in body.keys()}
    
    for key, value in body.items():
        if key in CRM_SYSTEM_CONFIG and key != "primary_team_lead":
            CRM_SYSTEM_CONFIG[key] = value

    await audit.log(
        action="system_settings.updated",
        entity_type="system_settings",
        actor_id=current_user.id,
        old_value=old_val,
        new_value=body,
    )
    return {"data": CRM_SYSTEM_CONFIG, "message": "System settings updated successfully."}


@router.post("/import/preview")
async def preview_lead_file(
    file: UploadFile = File(...),
    current_user: User = Depends(require_data_ops_or_above),
    db: AsyncSession = Depends(get_db),
):
    """
    Preview uploaded CSV/Excel file for lead ingestion.
    Returns detected headers, preview rows, and suggested column mapping.
    """
    content = await file.read()
    if not content:
        raise ValidationError("Uploaded file is empty.")

    service = FileImportService(db)
    result = await service.preview_import(content, file.filename or "upload.csv")
    return {"data": result}


@router.post("/import/commit")
async def commit_lead_file_import(
    file: UploadFile = File(...),
    mapping: Optional[str] = Form(None),
    current_user: User = Depends(require_data_ops_or_above),
    db: AsyncSession = Depends(get_db),
):
    """
    Execute full ingestion of uploaded CSV/Excel file into unassigned New Leads Pool.
    Follows identical idempotency, validation, and duplicate detection rules.
    """
    content = await file.read()
    if not content:
        raise ValidationError("Uploaded file is empty.")

    column_mapping = None
    if mapping:
        try:
            column_mapping = json.loads(mapping)
        except Exception:
            pass

    service = FileImportService(db)
    result = await service.execute_import(
        file_content=content,
        filename=file.filename or "upload.csv",
        column_mapping=column_mapping,
        user_id=current_user.id,
    )
    return {"data": result, "message": f"Successfully processed {result['total_processed']} rows."}


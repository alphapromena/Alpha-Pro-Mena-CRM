"""
Reports router — management dashboards, user performance breakdown, user drill-down, and team activity.
"""
import uuid
import math
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, select, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import get_current_user, require_manager_or_above, require_user_or_above
from app.database import get_db
from app.models.call import Call
from app.models.contact import Contact, ContactStatus
from app.models.company import Company
from app.models.demo import Demo, DemoStage
from app.models.opportunity import Opportunity, OpportunityStage, OpportunityRoadmapStep
from app.models.task import Task, TaskStatus, TaskType
from app.models.follow_up import FollowUp
from app.models.recall import Recall
from app.models.no_answer import NoAnswerQueue
from app.models.user import User, Team, UserRole
from app.models.audit import AuditLog
from app.models.activity import EmailActivity, WhatsAppActivity
from app.models.note import ContactNote

router = APIRouter(prefix="/reports", tags=["Reports"])


def is_past(dt_val: Optional[datetime], target_now: Optional[datetime] = None) -> bool:
    """Safely compare datetime values handling naive and tz-aware datetimes."""
    if not dt_val:
        return False
    now_dt = target_now or datetime.now(timezone.utc)
    if dt_val.tzinfo is None and now_dt.tzinfo is not None:
        dt_val = dt_val.replace(tzinfo=timezone.utc)
    elif dt_val.tzinfo is not None and now_dt.tzinfo is None:
        now_dt = now_dt.replace(tzinfo=timezone.utc)
    return dt_val < now_dt


def _parse_date_range(
    preset: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> tuple[datetime, datetime, str]:
    now = datetime.now(timezone.utc)
    today_start = datetime(now.year, now.month, now.day, 0, 0, 0, tzinfo=timezone.utc)
    
    if preset == "today":
        return today_start, now, "today"
    elif preset == "yesterday":
        yesterday_start = today_start - timedelta(days=1)
        yesterday_end = today_start - timedelta(microseconds=1)
        return yesterday_start, yesterday_end, "yesterday"
    elif preset == "this_week":
        # Monday as start of week
        start_week = today_start - timedelta(days=now.weekday())
        return start_week, now, "this_week"
    elif preset == "last_7_days":
        return now - timedelta(days=7), now, "last_7_days"
    elif preset == "this_month":
        start_month = datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=timezone.utc)
        return start_month, now, "this_month"
    elif preset == "all":
        return datetime(2020, 1, 1, tzinfo=timezone.utc), now, "all"
    elif date_from and date_to:
        df = datetime.fromisoformat(date_from)
        if df.tzinfo is None:
            df = df.replace(tzinfo=timezone.utc)
        dt = datetime.fromisoformat(date_to)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return df, dt, "custom"
    elif date_from:
        df = datetime.fromisoformat(date_from)
        if df.tzinfo is None:
            df = df.replace(tzinfo=timezone.utc)
        return df, now, "custom"
    else:
        # Default: this_month
        start_month = datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=timezone.utc)
        return start_month, now, "this_month"


def _calc_performance_score(
    calls: int,
    answered: int,
    interested: int,
    demos_done: int,
    opps_won: int,
    overdue_tasks: int,
) -> int:
    """
    Transparent performance rating (0-100 pts) based on:
    - Outreach Volume: up to 25 pts (100 calls = 25 pts)
    - Response & Interest Quality: up to 25 pts (interested rate)
    - Demo Conversions: up to 25 pts (demos completed)
    - Opportunity Conversions: up to 25 pts (opportunities won)
    - Overdue Penalty: -5 pts per overdue task (min score 0)
    """
    vol_pts = min(25.0, (calls / 100.0) * 25.0)
    
    interest_rate = (interested / max(1, answered)) if answered > 0 else 0.0
    quality_pts = min(25.0, interest_rate * 50.0)
    
    demo_pts = min(25.0, demos_done * 8.0)
    opp_pts = min(25.0, opps_won * 12.5)
    
    penalty = overdue_tasks * 5.0
    
    raw = vol_pts + quality_pts + demo_pts + opp_pts - penalty
    return max(0, min(100, int(round(raw))))


def _clean_param(val: Any) -> Optional[str]:
    if val is None or not isinstance(val, str):
        return None
    s = val.strip()
    return s if s else None


@router.get("/dashboard")
async def management_dashboard(
    preset: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    team_id: Optional[str] = Query(None),
    company_id: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    outcome: Optional[str] = Query(None),
    demo_stage: Optional[str] = Query(None),
    current_user: User = Depends(require_user_or_above),
    db: AsyncSession = Depends(get_db),
):
    """
    High-operational Management Dashboard:
    - Overall Team Totals across Calls, Emails, WhatsApp, Demos, Follow-ups, Recalls, Opps, Overdue Tasks
    - User-by-User Breakdown table with transparent conversion funnel & performance scores
    - Dynamic multi-filtering by date range, user, team, company, country, outcome, demo stage
    """
    preset = _clean_param(preset)
    date_from = _clean_param(date_from)
    date_to = _clean_param(date_to)
    user_id = _clean_param(user_id)
    team_id = _clean_param(team_id)
    company_id = _clean_param(company_id)
    country = _clean_param(country)
    outcome = _clean_param(outcome)
    demo_stage = _clean_param(demo_stage)

    df, dt, used_preset = _parse_date_range(preset, date_from, date_to)
    now = datetime.now(timezone.utc)

    # For sales reps (USER), scope metrics to their own records if no explicit user_id passed
    if (not current_user.is_manager_or_above) and (not user_id):
        user_id = str(current_user.id)

    # ── 1. Calls & Outreach Filtering ──────────────────────────────────────────
    call_stmt = select(Call).where(Call.called_at.between(df, dt))
    if user_id:
        call_stmt = call_stmt.where(Call.user_id == uuid.UUID(user_id))
    if outcome:
        call_stmt = call_stmt.where(Call.outcome == outcome)
    if company_id or country:
        call_stmt = call_stmt.join(Contact, Call.contact_id == Contact.id)
        if company_id:
            call_stmt = call_stmt.where(Contact.company_id == uuid.UUID(company_id))
        if country:
            call_stmt = call_stmt.where(Contact.country.ilike(f"%{country}%"))

    # Execute calls aggregation
    calls_rows = (await db.execute(call_stmt.options(selectinload(Call.contact).selectinload(Contact.company)))).scalars().all()
    total_calls = len(calls_rows)
    unique_contacts_called = len(set(c.contact_id for c in calls_rows))

    outcomes_count: Dict[str, int] = {}
    for c in calls_rows:
        outcomes_count[c.outcome] = outcomes_count.get(c.outcome, 0) + 1

    answered_calls = (
        outcomes_count.get("ANSWERED", 0)
        + outcomes_count.get("INTERESTED", 0)
        + outcomes_count.get("EMAIL_REQUESTED", 0)
        + outcomes_count.get("WHATSAPP_REQUESTED", 0)
        + outcomes_count.get("DEMO_REQUESTED", 0)
        + outcomes_count.get("MEETING_REQUESTED", 0)
        + outcomes_count.get("PROPOSAL_REQUESTED", 0)
        + outcomes_count.get("CALL_LATER", 0)
        + outcomes_count.get("NOT_INTERESTED", 0)
    )
    no_answer_calls = outcomes_count.get("NO_ANSWER", 0) + outcomes_count.get("BUSY", 0)
    interested_calls = outcomes_count.get("INTERESTED", 0)
    email_req_calls = outcomes_count.get("EMAIL_REQUESTED", 0)
    whatsapp_req_calls = outcomes_count.get("WHATSAPP_REQUESTED", 0)
    demo_req_calls = outcomes_count.get("DEMO_REQUESTED", 0)
    meeting_req_calls = outcomes_count.get("MEETING_REQUESTED", 0)
    proposal_req_calls = outcomes_count.get("PROPOSAL_REQUESTED", 0)

    # Total engaged / high-intent prospect calls across all outreach outcomes
    engaged_calls = (
        interested_calls
        + email_req_calls
        + whatsapp_req_calls
        + demo_req_calls
        + meeting_req_calls
        + proposal_req_calls
    )

    # ── COMPANY-LEVEL ENGAGEMENT & DEMO DEDUPLICATION ──────────────────────────
    # Demo Conversion must be calculated at Company level, NOT individual contact level.
    # If Company ELM has 50 contacts, 20 engaged, and 1 demo, it counts as 1 Company Demo / 1 Company Engaged (100%).
    engaged_outcomes = {"INTERESTED", "EMAIL_REQUESTED", "WHATSAPP_REQUESTED", "DEMO_REQUESTED", "MEETING_REQUESTED", "PROPOSAL_REQUESTED"}
    engaged_companies_set: set[str] = set()
    for c in calls_rows:
        if c.outcome in engaged_outcomes and c.contact:
            c_comp_id = c.contact.company_id
            c_key = str(c_comp_id) if c_comp_id else (c.contact.company.name.strip().lower() if c.contact.company and c.contact.company.name else f"ct_{c.contact_id}")
            engaged_companies_set.add(c_key)

    # ── 2. Emails & WhatsApp Activities ────────────────────────────────────────
    # Count direct activities + completed email/whatsapp tasks
    email_act_stmt = select(func.count(EmailActivity.id)).where(EmailActivity.sent_at.between(df, dt))
    if user_id:
        email_act_stmt = email_act_stmt.where(EmailActivity.user_id == uuid.UUID(user_id))
    email_act_count = (await db.execute(email_act_stmt)).scalar_one() or 0

    email_task_stmt = select(func.count(Task.id)).where(
        Task.type == TaskType.EMAIL,
        Task.status == TaskStatus.COMPLETED,
        Task.completed_at.between(df, dt),
    )
    if user_id:
        email_task_stmt = email_task_stmt.where(Task.assigned_to == uuid.UUID(user_id))
    email_task_count = (await db.execute(email_task_stmt)).scalar_one() or 0
    total_emails = email_act_count + email_task_count + email_req_calls

    whatsapp_act_stmt = select(func.count(WhatsAppActivity.id)).where(WhatsAppActivity.sent_at.between(df, dt))
    if user_id:
        whatsapp_act_stmt = whatsapp_act_stmt.where(WhatsAppActivity.user_id == uuid.UUID(user_id))
    whatsapp_act_count = (await db.execute(whatsapp_act_stmt)).scalar_one() or 0

    whatsapp_task_stmt = select(func.count(Task.id)).where(
        Task.type == TaskType.WHATSAPP,
        Task.status == TaskStatus.COMPLETED,
        Task.completed_at.between(df, dt),
    )
    if user_id:
        whatsapp_task_stmt = whatsapp_task_stmt.where(Task.assigned_to == uuid.UUID(user_id))
    whatsapp_task_count = (await db.execute(whatsapp_task_stmt)).scalar_one() or 0
    total_whatsapp = whatsapp_act_count + whatsapp_task_count + whatsapp_req_calls

    # ── 3. Demos Breakdown (Company Level) ──────────────────────────────────────
    demo_stmt = select(Demo).where(Demo.created_at.between(df, dt)).options(selectinload(Demo.contact).selectinload(Contact.company), selectinload(Demo.company))
    if user_id:
        demo_stmt = demo_stmt.where(Demo.owner_id == uuid.UUID(user_id))
    if company_id:
        demo_stmt = demo_stmt.where(Demo.company_id == uuid.UUID(company_id))
    if demo_stage:
        demo_stmt = demo_stmt.where(Demo.stage == demo_stage)

    demo_rows = (await db.execute(demo_stmt)).scalars().all()
    demos_agreed = len([d for d in demo_rows if d.stage in ["REQUESTED", "SCHEDULED"]]) + demo_req_calls
    demos_completed = len([d for d in demo_rows if d.stage == "COMPLETED"])
    demos_cancelled = len([d for d in demo_rows if d.stage in ["CANCELLED", "NO_SHOW"]])
    demos_total = demos_agreed + demos_completed + demos_cancelled

    # Deduplicate unique companies that reached Demo
    demo_companies_set: set[str] = set()
    for d in demo_rows:
        d_comp_id = d.company_id or (d.contact.company_id if d.contact else None)
        d_key = str(d_comp_id) if d_comp_id else (d.company.name.strip().lower() if d.company and d.company.name else (d.contact.company.name.strip().lower() if d.contact and d.contact.company and d.contact.company.name else f"ct_{d.contact_id}"))
        demo_companies_set.add(d_key)
    for c in calls_rows:
        if c.outcome == "DEMO_REQUESTED" and c.contact:
            c_comp_id = c.contact.company_id
            c_key = str(c_comp_id) if c_comp_id else (c.contact.company.name.strip().lower() if c.contact and c.contact.company and c.contact.company.name else f"ct_{c.contact_id}")
            demo_companies_set.add(c_key)

    unique_engaged_companies_count = len(engaged_companies_set)
    unique_demo_companies_count = len(demo_companies_set)

    # ── 4. Follow-ups & Recalls ────────────────────────────────────────────────
    fu_stmt = select(FollowUp).where(FollowUp.created_at.between(df, dt))
    if user_id:
        fu_stmt = fu_stmt.where(FollowUp.user_id == uuid.UUID(user_id))
    fu_rows = (await db.execute(fu_stmt)).scalars().all()
    total_follow_ups = len(fu_rows)
    pending_follow_ups = len([f for f in fu_rows if f.status == "PENDING"])
    overdue_follow_ups = len([f for f in fu_rows if f.status == "PENDING" and is_past(f.due_at, now)])

    recall_stmt = select(Recall).where(Recall.created_at.between(df, dt))
    if user_id:
        recall_stmt = recall_stmt.where(Recall.user_id == uuid.UUID(user_id))
    recall_rows = (await db.execute(recall_stmt)).scalars().all()
    total_recalls = len(recall_rows) + outcomes_count.get("CALL_LATER", 0)
    pending_recalls = len([r for r in recall_rows if r.status == "PENDING"])
    overdue_recalls = len([r for r in recall_rows if r.status == "PENDING" and is_past(r.scheduled_at, now)])

    # ── 5. Opportunities & Pipeline ───────────────────────────────────────────
    opp_stmt = select(Opportunity).where(
        Opportunity.deleted_at.is_(None),
        Opportunity.created_at.between(df, dt),
    )
    if user_id:
        opp_stmt = opp_stmt.where(Opportunity.owner_id == uuid.UUID(user_id))
    if company_id:
        opp_stmt = opp_stmt.where(Opportunity.company_id == uuid.UUID(company_id))

    opp_rows = (await db.execute(opp_stmt)).scalars().all()
    opps_new = len(opp_rows)
    opps_won = len([o for o in opp_rows if o.stage == OpportunityStage.WON])
    opps_lost = len([o for o in opp_rows if o.stage == OpportunityStage.LOST])
    total_pipeline_val = sum((o.value or 0.0) for o in opp_rows)
    won_pipeline_val = sum((o.value or 0.0) for o in opp_rows if o.stage == OpportunityStage.WON)

    # ── 6. Tasks & Overdue Tasks ───────────────────────────────────────────────
    task_stmt = select(Task).where(Task.created_at.between(df, dt))
    if user_id:
        task_stmt = task_stmt.where(Task.assigned_to == uuid.UUID(user_id))
    task_rows = (await db.execute(task_stmt)).scalars().all()
    total_tasks = len(task_rows)
    open_tasks = len([t for t in task_rows if t.status in [TaskStatus.OPEN, TaskStatus.IN_PROGRESS]])

    overdue_stmt = select(func.count(Task.id)).where(
        Task.due_at < now,
        Task.status.in_([TaskStatus.OPEN, TaskStatus.IN_PROGRESS, TaskStatus.OVERDUE]),
    )
    if user_id:
        overdue_stmt = overdue_stmt.where(Task.assigned_to == uuid.UUID(user_id))
    overdue_tasks_count = (await db.execute(overdue_stmt)).scalar_one() or 0

    # ── 7. Total Contacts in Scope ────────────────────────────────────────────
    base_contact_stmt = select(func.count(Contact.id)).where(Contact.deleted_at.is_(None))
    if user_id:
        base_contact_stmt = base_contact_stmt.where(Contact.owner_id == uuid.UUID(user_id))
    if country:
        base_contact_stmt = base_contact_stmt.where(Contact.country.ilike(f"%{country}%"))
    
    total_contacts_count = (await db.execute(base_contact_stmt)).scalar_one() or 0

    # Active operational contacts (in working queue, not archived, not personal pool, not unassigned)
    active_contacts_stmt = select(func.count(Contact.id)).where(
        Contact.deleted_at.is_(None),
        Contact.status.not_in([ContactStatus.ARCHIVED, ContactStatus.PENDING_CLAIM, ContactStatus.UNASSIGNED]),
    )
    if user_id:
        active_contacts_stmt = active_contacts_stmt.where(Contact.owner_id == uuid.UUID(user_id))
    if country:
        active_contacts_stmt = active_contacts_stmt.where(Contact.country.ilike(f"%{country}%"))
    active_leads_count = (await db.execute(active_contacts_stmt)).scalar_one() or 0

    # Archived contacts
    archived_contacts_stmt = select(func.count(Contact.id)).where(
        Contact.deleted_at.is_(None),
        Contact.status == ContactStatus.ARCHIVED,
    )
    if user_id:
        archived_contacts_stmt = archived_contacts_stmt.where(Contact.owner_id == uuid.UUID(user_id))
    archived_contacts_count = (await db.execute(archived_contacts_stmt)).scalar_one() or 0

    # Personal Pool (pending claim by sales rep)
    personal_pool_stmt = select(func.count(Contact.id)).where(
        Contact.deleted_at.is_(None),
        Contact.status == ContactStatus.PENDING_CLAIM,
    )
    if user_id:
        personal_pool_stmt = personal_pool_stmt.where(Contact.owner_id == uuid.UUID(user_id))
    personal_pool_count = (await db.execute(personal_pool_stmt)).scalar_one() or 0

    # Unassigned leads
    unassigned_leads_count = (await db.execute(
        select(func.count(Contact.id)).where(
            Contact.deleted_at.is_(None),
            or_(Contact.owner_id.is_(None), Contact.status == ContactStatus.UNASSIGNED)
        )
    )).scalar_one() or 0

    # ── 8. Conversion Funnel Percentages (Company-Level Demo Conversion) ─────
    # Each rate returns None when the denominator is 0 so the UI can show "—"
    # instead of a misleading 0% that contradicts the displayed X/Y fraction.
    answer_rate = round((answered_calls / total_calls) * 100, 1) if total_calls > 0 else None
    calls_to_interested = round((engaged_calls / answered_calls) * 100, 1) if answered_calls > 0 else None
    # Demo conversion is strictly unique engaged companies -> unique companies reaching demo
    interested_to_demo = round((unique_demo_companies_count / unique_engaged_companies_count) * 100, 1) if unique_engaged_companies_count > 0 else None
    demo_to_opp = round((opps_new / demos_completed) * 100, 1) if demos_completed > 0 else None

    # ── 9. User-by-User Breakdown ─────────────────────────────────────────────
    users_stmt = select(User).where(User.is_active.is_(True), User.deleted_at.is_(None)).options(selectinload(User.team))
    if team_id:
        users_stmt = users_stmt.where(User.team_id == uuid.UUID(team_id))
    users_list = (await db.execute(users_stmt)).scalars().all()

    # Pre-fetch all calls in period grouped by user
    user_calls_map: Dict[str, List[Call]] = {}
    all_period_calls = (await db.execute(
        select(Call)
        .where(Call.called_at.between(df, dt))
        .options(selectinload(Call.contact).selectinload(Contact.company))
    )).scalars().all()
    for c in all_period_calls:
        if c.user_id:
            uid_str = str(c.user_id)
            user_calls_map.setdefault(uid_str, []).append(c)

    # Pre-fetch all demos in period
    user_demos_map: Dict[str, List[Demo]] = {}
    all_period_demos = (await db.execute(
        select(Demo)
        .where(Demo.created_at.between(df, dt))
        .options(selectinload(Demo.contact).selectinload(Contact.company), selectinload(Demo.company))
    )).scalars().all()
    for d in all_period_demos:
        if d.owner_id:
            uid_str = str(d.owner_id)
            user_demos_map.setdefault(uid_str, []).append(d)

    # Pre-fetch all opportunities in period
    user_opps_map: Dict[str, List[Opportunity]] = {}
    all_period_opps = (await db.execute(select(Opportunity).where(Opportunity.deleted_at.is_(None), Opportunity.created_at.between(df, dt)))).scalars().all()
    for o in all_period_opps:
        if o.owner_id:
            uid_str = str(o.owner_id)
            user_opps_map.setdefault(uid_str, []).append(o)

    # Pre-fetch all overdue tasks per user
    user_overdue_map: Dict[str, int] = {}
    overdue_by_user = (await db.execute(
        select(Task.assigned_to, func.count(Task.id))
        .where(
            Task.due_at < now,
            Task.status.in_([TaskStatus.OPEN, TaskStatus.IN_PROGRESS, TaskStatus.OVERDUE]),
        )
        .group_by(Task.assigned_to)
    )).all()
    for row in overdue_by_user:
        if row[0]:
            user_overdue_map[str(row[0])] = row[1]

    # Pre-fetch follow-ups and recalls per user
    user_fu_map: Dict[str, int] = {}
    fu_by_user = (await db.execute(
        select(FollowUp.user_id, func.count(FollowUp.id))
        .where(FollowUp.created_at.between(df, dt))
        .group_by(FollowUp.user_id)
    )).all()
    for row in fu_by_user:
        if row[0]:
            user_fu_map[str(row[0])] = row[1]

    user_recall_map: Dict[str, int] = {}
    recalls_by_user = (await db.execute(
        select(Recall.user_id, func.count(Recall.id))
        .where(Recall.created_at.between(df, dt))
        .group_by(Recall.user_id)
    )).all()
    for row in recalls_by_user:
        if row[0]:
            user_recall_map[str(row[0])] = row[1]

    # Build detailed per-user summary
    user_breakdown = []
    team_members_map: Dict[str, List[dict]] = {}

    for u in users_list:
        # Operational Performance Evaluation & Oversight section must ONLY ever show the 4 sales reps (Saleh, Hasan, Amin, Ghaida)
        # Never Qusai (team lead) or Abdallah (manager)
        if u.role != UserRole.USER and u.first_name not in ["Saleh", "Hasan", "Amin", "Ghaida"]:
            continue
        if u.first_name in ["Qusai", "Abdallah"]:
            continue

        uid_str = str(u.id)
        u_calls = user_calls_map.get(uid_str, [])
        u_total_calls = len(u_calls)
        
        u_outcomes: Dict[str, int] = {}
        for c in u_calls:
            u_outcomes[c.outcome] = u_outcomes.get(c.outcome, 0) + 1
            
        u_answered = (
            u_outcomes.get("ANSWERED", 0)
            + u_outcomes.get("INTERESTED", 0)
            + u_outcomes.get("EMAIL_REQUESTED", 0)
            + u_outcomes.get("WHATSAPP_REQUESTED", 0)
            + u_outcomes.get("DEMO_REQUESTED", 0)
            + u_outcomes.get("MEETING_REQUESTED", 0)
            + u_outcomes.get("PROPOSAL_REQUESTED", 0)
            + u_outcomes.get("CALL_LATER", 0)
            + u_outcomes.get("NOT_INTERESTED", 0)
        )
        u_interested = (
            u_outcomes.get("INTERESTED", 0)
            + u_outcomes.get("EMAIL_REQUESTED", 0)
            + u_outcomes.get("WHATSAPP_REQUESTED", 0)
            + u_outcomes.get("DEMO_REQUESTED", 0)
            + u_outcomes.get("MEETING_REQUESTED", 0)
            + u_outcomes.get("PROPOSAL_REQUESTED", 0)
        )
        u_emails = u_outcomes.get("EMAIL_REQUESTED", 0)
        u_whatsapp = u_outcomes.get("WHATSAPP_REQUESTED", 0)
        
        u_demos = user_demos_map.get(uid_str, [])
        u_demo_agreed = len(u_demos) + u_outcomes.get("DEMO_REQUESTED", 0)
        u_demo_done = len([d for d in u_demos if d.stage == "COMPLETED"])
        u_demo_cancelled = len([d for d in u_demos if d.stage == "CANCELLED"])

        # Company-level engagement & demo counting per user
        u_engaged_comp_set: set[str] = set()
        for c in u_calls:
            if c.outcome in engaged_outcomes and c.contact:
                uc_comp_id = c.contact.company_id
                uc_key = str(uc_comp_id) if uc_comp_id else (c.contact.company.name.strip().lower() if c.contact.company and c.contact.company.name else f"ct_{c.contact_id}")
                u_engaged_comp_set.add(uc_key)

        u_demo_comp_set: set[str] = set()
        for d in u_demos:
            ud_comp_id = d.company_id or (d.contact.company_id if d.contact else None)
            ud_key = str(ud_comp_id) if ud_comp_id else (d.company.name.strip().lower() if d.company and d.company.name else (d.contact.company.name.strip().lower() if d.contact and d.contact.company and d.contact.company.name else f"ct_{d.contact_id}"))
            u_demo_comp_set.add(ud_key)
        for c in u_calls:
            if c.outcome == "DEMO_REQUESTED" and c.contact:
                uc_comp_id = c.contact.company_id
                uc_key = str(uc_comp_id) if uc_comp_id else (c.contact.company.name.strip().lower() if c.contact and c.contact.company and c.contact.company.name else f"ct_{c.contact_id}")
                u_demo_comp_set.add(uc_key)

        u_demo_conversion_rate = round((len(u_demo_comp_set) / len(u_engaged_comp_set)) * 100, 1) if len(u_engaged_comp_set) > 0 else None
        
        u_opps = user_opps_map.get(uid_str, [])
        u_opps_count = len(u_opps)
        u_opps_won = len([o for o in u_opps if o.stage == OpportunityStage.WON])
        u_opps_pipeline = sum(o.value or 0 for o in u_opps)
        u_opps_won_val = sum(o.value or 0 for o in u_opps if o.stage == OpportunityStage.WON)
        
        u_overdue = user_overdue_map.get(uid_str, 0)
        u_fu_count = user_fu_map.get(uid_str, 0)
        u_recall_count = user_recall_map.get(uid_str, 0)
        
        # Transparent performance score calculation
        score = _calc_performance_score(
            calls=u_total_calls,
            answered=u_answered,
            interested=u_interested,
            demos_done=u_demo_done,
            opps_won=u_opps_won,
            overdue_tasks=u_overdue,
        )
        
        u_ans_rate = round((u_answered / u_total_calls) * 100, 1) if u_total_calls > 0 else None
        u_int_rate = round((u_interested / u_answered) * 100, 1) if u_answered > 0 else None
        
        u_record = {
            "user_id": uid_str,
            "user_name": u.first_name,  # First name only as explicitly required
            "first_name": u.first_name,
            "full_name": u.full_name,
            "email": u.email,
            "role": u.role.value if hasattr(u.role, 'value') else u.role,
            "team_id": str(u.team_id) if u.team_id else None,
            "team_name": u.team.name if u.team else None,
            "calls": u_total_calls,
            "answered": u_answered,
            "interested": u_interested,
            "emails": u_emails,
            "whatsapp": u_whatsapp,
            "demo_agreed": u_demo_agreed,
            "demo_done": u_demo_done,
            "demo_cancelled": u_demo_cancelled,
            "unique_engaged_companies": len(u_engaged_comp_set),
            "unique_demo_companies": len(u_demo_comp_set),
            "follow_ups": u_fu_count,
            "recalls": u_recall_count,
            "opportunities": u_opps_count,
            "opportunities_won": u_opps_won,
            "pipeline_value": u_opps_pipeline,
            "won_value": u_opps_won_val,
            "overdue_tasks": u_overdue,
            "performance_score": score,
            "answer_rate": u_ans_rate,
            "interest_rate": u_int_rate,
            "conversions": {
                "answer_rate": u_ans_rate,
                "calls_to_interested": u_int_rate,
                "interested_to_demo": u_demo_conversion_rate,
                "demo_to_opportunity": round((u_opps_count / u_demo_done) * 100, 1) if u_demo_done > 0 else None,
            }
        }
        user_breakdown.append(u_record)
        if u.team_id:
            team_members_map.setdefault(str(u.team_id), []).append(u_record)

    # Sort users by performance score descending
    user_breakdown.sort(key=lambda x: (x["performance_score"], x["calls"]), reverse=True)

    # ── 10. Manager & Team Evaluation Summary ─────────────────────────────────
    teams_stmt = select(Team).where(Team.deleted_at.is_(None)).options(selectinload(Team.manager), selectinload(Team.members))
    teams_list = (await db.execute(teams_stmt)).scalars().all()
    manager_breakdown = []

    for t in teams_list:
        tid_str = str(t.id)
        m_members = team_members_map.get(tid_str, [])
        m_calls = sum(m["calls"] for m in m_members)
        m_answered = sum(m["answered"] for m in m_members)
        m_interested = sum(m["interested"] for m in m_members)
        m_emails = sum(m["emails"] for m in m_members)
        m_whatsapp = sum(m["whatsapp"] for m in m_members)
        m_demos = sum(m["demo_agreed"] for m in m_members)
        m_demos_done = sum(m["demo_done"] for m in m_members)
        m_opps = sum(m["opportunities"] for m in m_members)
        m_opps_won = sum(m["opportunities_won"] for m in m_members)
        m_pipeline = sum(m["pipeline_value"] for m in m_members)
        m_won = sum(m["won_value"] for m in m_members)
        m_overdue = sum(m["overdue_tasks"] for m in m_members)
        m_fu = sum(m["follow_ups"] for m in m_members)
        
        m_ans_rate = round((m_answered / max(1, m_calls)) * 100, 1) if m_calls > 0 else 0.0
        m_int_rate = round((m_interested / max(1, m_answered)) * 100, 1) if m_answered > 0 else 0.0
        m_score = _calc_performance_score(m_calls, m_answered, m_interested, m_demos_done, m_opps_won, m_overdue)

        manager_breakdown.append({
            "team_id": tid_str,
            "team_name": t.name,
            "manager_id": str(t.manager_id) if t.manager_id else None,
            "manager_name": t.manager.full_name if t.manager else "Unassigned",
            "manager_email": t.manager.email if t.manager else None,
            "members_count": len(m_members),
            "calls": m_calls,
            "answered": m_answered,
            "interested": m_interested,
            "emails": m_emails,
            "whatsapp": m_whatsapp,
            "demos_agreed": m_demos,
            "demos_completed": m_demos_done,
            "opportunities_count": m_opps,
            "opportunities_won": m_opps_won,
            "pipeline_value": m_pipeline,
            "won_value": m_won,
            "follow_ups": m_fu,
            "overdue_tasks": m_overdue,
            "answer_rate": m_ans_rate,
            "interest_rate": m_int_rate,
            "team_performance_score": m_score,
        })

    manager_breakdown.sort(key=lambda x: (x["team_performance_score"], x["calls"]), reverse=True)

    return {
        "data": {
            "period": {
                "from": df.isoformat(),
                "to": dt.isoformat(),
                "preset": used_preset,
            },
            "kpis": {
                "total_calls": total_calls,
                "unique_contacts": unique_contacts_called,
                "emails": total_emails,
                "whatsapp": total_whatsapp,
                "demo_agreed": demos_agreed,
                "demo_completed": demos_completed,
                "demo_cancelled": demos_cancelled,
                "follow_ups": total_follow_ups,
                "pending_follow_ups": pending_follow_ups,
                "overdue_follow_ups": overdue_follow_ups,
                "recalls": total_recalls,
                "pending_recalls": pending_recalls,
                "overdue_recalls": overdue_recalls,
                "opportunities": opps_new,
                "opportunities_won": opps_won,
                "opportunities_lost": opps_lost,
                "pipeline_value": total_pipeline_val,
                "won_value": won_pipeline_val,
                "overdue_tasks": overdue_tasks_count,
                "total_contacts": total_contacts_count,
                "unique_engaged_companies": unique_engaged_companies_count,
                "unique_demo_companies": unique_demo_companies_count,
                "unassigned_leads": unassigned_leads_count,
                "active_leads": active_leads_count,
                "archived_contacts": archived_contacts_count,
                "personal_pool_leads": personal_pool_count,
            },
            "calls_breakdown": {
                "total": total_calls,
                "answered": answered_calls,
                "no_answer": no_answer_calls,
                "interested": interested_calls,
                "email_requested": email_req_calls,
                "whatsapp_requested": whatsapp_req_calls,
                "demo_requested": demo_req_calls,
                "call_later": outcomes_count.get("CALL_LATER", 0),
                "by_outcome": outcomes_count,
            },
            "conversion_metrics": {
                "answer_rate": answer_rate,
                "calls_to_interested": calls_to_interested,
                "interested_to_demo": interested_to_demo,
                "demo_to_opportunity": demo_to_opp,
            },
            "user_performance": user_breakdown,
            "manager_performance": manager_breakdown,
        }
    }


@router.get("/user-drilldown/{target_user_id}")
async def user_drilldown(
    target_user_id: uuid.UUID,
    preset: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    current_user: User = Depends(require_manager_or_above),
    db: AsyncSession = Depends(get_db),
):
    """
    Detailed operational dossier for any user:
    Manager can inspect an employee's work without logging into their account.
    """
    df, dt, used_preset = _parse_date_range(preset, date_from, date_to)
    now = datetime.now(timezone.utc)

    # 1. Fetch User
    u_stmt = select(User).where(User.id == target_user_id).options(selectinload(User.team))
    user_obj = (await db.execute(u_stmt)).scalar_one_or_none()
    if not user_obj:
        return {"error": "User not found"}

    # 2. Calls by this user
    call_stmt = (
        select(Call)
        .where(Call.user_id == target_user_id, Call.called_at.between(df, dt))
        .options(selectinload(Call.contact).selectinload(Contact.company))
        .order_by(Call.called_at.desc())
    )
    user_calls = (await db.execute(call_stmt)).scalars().all()
    
    outcomes: Dict[str, int] = {}
    for c in user_calls:
        outcomes[c.outcome] = outcomes.get(c.outcome, 0) + 1

    # 3. Assigned Contacts
    contacts_stmt = (
        select(Contact)
        .where(Contact.owner_id == target_user_id, Contact.deleted_at.is_(None))
        .options(selectinload(Contact.company))
        .order_by(Contact.last_contact_at.desc().nullslast())
        .limit(20)
    )
    contacts_list = (await db.execute(contacts_stmt)).scalars().all()
    total_assigned_contacts = (await db.execute(
        select(func.count(Contact.id)).where(Contact.owner_id == target_user_id, Contact.deleted_at.is_(None))
    )).scalar_one() or 0

    # 4. Tasks (Open, Overdue, Completed)
    tasks_stmt = (
        select(Task)
        .where(Task.assigned_to == target_user_id)
        .options(selectinload(Task.contact))
        .order_by(Task.due_at.asc().nullslast())
    )
    all_user_tasks = (await db.execute(tasks_stmt)).scalars().all()
    open_tasks = [t for t in all_user_tasks if t.status in [TaskStatus.OPEN, TaskStatus.IN_PROGRESS]]
    overdue_tasks = [t for t in open_tasks if is_past(t.due_at, now)]
    completed_tasks = [t for t in all_user_tasks if t.status == TaskStatus.COMPLETED]

    # 5. Demos
    demos_stmt = (
        select(Demo)
        .where(Demo.owner_id == target_user_id)
        .options(selectinload(Demo.contact), selectinload(Demo.company))
        .order_by(Demo.scheduled_at.desc().nullslast())
    )
    user_demos = (await db.execute(demos_stmt)).scalars().all()

    # 6. Opportunities
    opps_stmt = (
        select(Opportunity)
        .where(Opportunity.owner_id == target_user_id, Opportunity.deleted_at.is_(None))
        .options(selectinload(Opportunity.company))
        .order_by(Opportunity.created_at.desc())
    )
    user_opps = (await db.execute(opps_stmt)).scalars().all()

    # 7. Recalls & No Answer Queue
    recalls_stmt = (
        select(Recall)
        .where(Recall.user_id == target_user_id)
        .options(selectinload(Recall.contact))
        .order_by(Recall.scheduled_at.asc())
    )
    user_recalls = (await db.execute(recalls_stmt)).scalars().all()

    no_ans_stmt = (
        select(NoAnswerQueue)
        .where(NoAnswerQueue.user_id == target_user_id)
        .options(selectinload(NoAnswerQueue.contact))
        .order_by(NoAnswerQueue.next_attempt_at.asc())
    )
    user_no_answers = (await db.execute(no_ans_stmt)).scalars().all()

    # 8. Activity Timeline for this user
    timeline_items = []
    for c in user_calls[:25]:
        timeline_items.append({
            "type": "call",
            "id": str(c.id),
            "timestamp": c.called_at.isoformat(),
            "contact_name": c.contact.full_name if c.contact else "Unknown",
            "company_name": c.contact.company.name if (c.contact and c.contact.company) else None,
            "outcome": c.outcome,
            "duration_seconds": c.duration_seconds,
            "notes": c.notes,
        })
    for t in completed_tasks[:15]:
        timeline_items.append({
            "type": "task_completed",
            "id": str(t.id),
            "timestamp": t.completed_at.isoformat() if t.completed_at else t.created_at.isoformat(),
            "contact_name": t.contact.full_name if t.contact else None,
            "title": t.title,
            "task_type": t.type,
            "notes": t.completion_notes,
        })
    for d in user_demos[:10]:
        timeline_items.append({
            "type": "demo",
            "id": str(d.id),
            "timestamp": d.scheduled_at.isoformat() if d.scheduled_at else d.created_at.isoformat(),
            "contact_name": d.contact.full_name if d.contact else None,
            "company_name": d.company.name if d.company else None,
            "stage": d.stage,
            "notes": d.notes,
        })
    timeline_items.sort(key=lambda x: x["timestamp"], reverse=True)

    # Calculate individual score
    score = _calc_performance_score(
        calls=len(user_calls),
        answered=len([c for c in user_calls if c.outcome in ["ANSWERED", "INTERESTED", "EMAIL_REQUESTED", "WHATSAPP_REQUESTED", "DEMO_REQUESTED"]]),
        interested=outcomes.get("INTERESTED", 0),
        demos_done=len([d for d in user_demos if d.stage == "COMPLETED"]),
        opps_won=len([o for o in user_opps if o.stage == OpportunityStage.WON]),
        overdue_tasks=len(overdue_tasks),
    )

    return {
        "data": {
            "user": {
                "id": str(user_obj.id),
                "full_name": user_obj.full_name,
                "email": user_obj.email,
                "role": user_obj.role.value if hasattr(user_obj.role, 'value') else user_obj.role,
                "team_name": user_obj.team.name if user_obj.team else None,
                "lead_capacity": user_obj.lead_capacity,
                "last_login_at": user_obj.last_login_at.isoformat() if user_obj.last_login_at else None,
            },
            "performance_score": score,
            "summary_kpis": {
                "total_calls": len(user_calls),
                "unique_contacts": len(set(c.contact_id for c in user_calls)),
                "interested": outcomes.get("INTERESTED", 0),
                "emails": outcomes.get("EMAIL_REQUESTED", 0),
                "whatsapp": outcomes.get("WHATSAPP_REQUESTED", 0),
                "demos_total": len(user_demos),
                "demos_completed": len([d for d in user_demos if d.stage == "COMPLETED"]),
                "opportunities": len(user_opps),
                "assigned_contacts": total_assigned_contacts,
                "open_tasks": len(open_tasks),
                "overdue_tasks": len(overdue_tasks),
            },
            "calls_by_outcome": outcomes,
            "recent_calls": [
                {
                    "id": str(c.id),
                    "called_at": c.called_at.isoformat(),
                    "contact_id": str(c.contact_id),
                    "contact_name": c.contact.full_name if c.contact else "Unknown",
                    "company_name": c.contact.company.name if (c.contact and c.contact.company) else None,
                    "phone": c.contact.phone if c.contact else None,
                    "outcome": c.outcome,
                    "duration_seconds": c.duration_seconds,
                    "notes": c.notes,
                }
                for c in user_calls[:20]
            ],
            "assigned_contacts": [
                {
                    "id": str(ct.id),
                    "full_name": ct.full_name,
                    "company_name": ct.company.name if ct.company else None,
                    "position": ct.position,
                    "phone": ct.phone,
                    "email": ct.email,
                    "status": ct.status,
                    "attempt_count": ct.attempt_count or 0,
                    "last_outcome": ct.last_outcome,
                    "last_contact_at": ct.last_contact_at.isoformat() if ct.last_contact_at else None,
                }
                for ct in contacts_list
            ],
            "tasks": [
                {
                    "id": str(t.id),
                    "title": t.title,
                    "type": t.type,
                    "priority": t.priority,
                    "status": t.status,
                    "due_at": t.due_at.isoformat() if t.due_at else None,
                    "contact_name": t.contact.full_name if t.contact else None,
                }
                for t in all_user_tasks[:20]
            ],
            "demos": [
                {
                    "id": str(d.id),
                    "stage": d.stage,
                    "scheduled_at": d.scheduled_at.isoformat() if d.scheduled_at else None,
                    "company_name": d.company.name if d.company else None,
                    "contact_name": d.contact.full_name if d.contact else None,
                    "result": d.result,
                }
                for d in user_demos
            ],
            "opportunities": [
                {
                    "id": str(o.id),
                    "title": o.title,
                    "value": o.value,
                    "stage": o.stage,
                    "probability": o.probability,
                    "company_name": o.company.name if o.company else None,
                }
                for o in user_opps
            ],
            "recalls": [
                {
                    "id": str(r.id),
                    "contact_name": r.contact.full_name if r.contact else None,
                    "scheduled_at": r.scheduled_at.isoformat(),
                    "notes": r.notes,
                    "status": r.status,
                }
                for r in user_recalls
            ],
            "no_answer": [
                {
                    "id": str(na.id),
                    "contact_name": na.contact.full_name if na.contact else None,
                    "attempt_number": na.attempt_number,
                    "next_attempt_at": na.next_attempt_at.isoformat() if na.next_attempt_at else None,
                }
                for na in user_no_answers
            ],
            "activity_timeline": timeline_items,
        }
    }


@router.get("/team-activity")
async def team_activity(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    preset: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    activity_type: Optional[str] = Query(None),
    current_user: User = Depends(require_manager_or_above),
    db: AsyncSession = Depends(get_db),
):
    """
    Live chronological stream of all team activities for management oversight.
    """
    df, dt, _ = _parse_date_range(preset, date_from, date_to)

    items: List[Dict[str, Any]] = []

    # 1. Calls
    if not activity_type or activity_type in ["CALL", "ALL"]:
        call_q = (
            select(Call)
            .where(Call.called_at.between(df, dt))
            .options(selectinload(Call.user), selectinload(Call.contact).selectinload(Contact.company))
            .order_by(Call.called_at.desc())
            .limit(100)
        )
        if user_id:
            call_q = call_q.where(Call.user_id == uuid.UUID(user_id))
        calls = (await db.execute(call_q)).scalars().all()
        for c in calls:
            items.append({
                "type": "CALL",
                "id": str(c.id),
                "timestamp": c.called_at.isoformat(),
                "actor_id": str(c.user_id) if c.user_id else None,
                "actor_name": c.user.full_name if c.user else "Sales Agent",
                "title": f"{c.user.first_name if c.user else 'Agent'} called {c.contact.full_name if c.contact else 'Contact'}",
                "subtitle": c.contact.company.name if (c.contact and c.contact.company) else None,
                "outcome": c.outcome,
                "notes": c.notes,
                "details": f"Duration: {c.duration_seconds or 0}s | Attempt #{c.attempt_number or 1}",
                "link": f"/contacts/{c.contact_id}" if c.contact_id else None,
            })

    # 2. Tasks completed
    if not activity_type or activity_type in ["TASK", "ALL"]:
        task_q = (
            select(Task)
            .where(Task.completed_at.is_not(None), Task.completed_at.between(df, dt))
            .options(selectinload(Task.assignee), selectinload(Task.contact).selectinload(Contact.company))
            .order_by(Task.completed_at.desc())
            .limit(100)
        )
        if user_id:
            task_q = task_q.where(Task.assigned_to == uuid.UUID(user_id))
        tasks = (await db.execute(task_q)).scalars().all()
        for t in tasks:
            items.append({
                "type": "TASK_COMPLETED",
                "id": str(t.id),
                "timestamp": t.completed_at.isoformat() if t.completed_at else t.created_at.isoformat(),
                "actor_id": str(t.assigned_to) if t.assigned_to else None,
                "actor_name": t.assignee.full_name if t.assignee else "Sales Agent",
                "title": f"{t.assignee.first_name if t.assignee else 'Agent'} completed {t.type.lower()} task: '{t.title}'",
                "subtitle": t.contact.full_name if t.contact else None,
                "outcome": "COMPLETED",
                "notes": t.completion_notes,
                "details": f"Priority: {t.priority} | Type: {t.type}",
                "link": f"/contacts/{t.contact_id}" if t.contact_id else "/tasks",
            })

    # 3. Demos
    if not activity_type or activity_type in ["DEMO", "ALL"]:
        demo_q = (
            select(Demo)
            .where(Demo.created_at.between(df, dt))
            .options(selectinload(Demo.contact), selectinload(Demo.company))
            .order_by(Demo.created_at.desc())
            .limit(100)
        )
        if user_id:
            demo_q = demo_q.where(Demo.owner_id == uuid.UUID(user_id))
        demos = (await db.execute(demo_q)).scalars().all()
        for d in demos:
            items.append({
                "type": "DEMO",
                "id": str(d.id),
                "timestamp": d.created_at.isoformat(),
                "actor_id": str(d.owner_id) if d.owner_id else None,
                "actor_name": "Sales Team",
                "title": f"Demo stage updated to '{d.stage}' with {d.company.name if d.company else 'Account'}",
                "subtitle": d.contact.full_name if d.contact else None,
                "outcome": d.stage,
                "notes": d.notes or d.result,
                "details": f"Scheduled: {d.scheduled_at.isoformat() if d.scheduled_at else 'TBD'}",
                "link": f"/demos",
            })

    # 4. Opportunity Roadmap steps
    if not activity_type or activity_type in ["OPPORTUNITY", "ALL"]:
        road_q = (
            select(OpportunityRoadmapStep)
            .where(OpportunityRoadmapStep.created_at.between(df, dt))
            .options(selectinload(OpportunityRoadmapStep.user), selectinload(OpportunityRoadmapStep.contact))
            .order_by(OpportunityRoadmapStep.created_at.desc())
            .limit(100)
        )
        if user_id:
            road_q = road_q.where(OpportunityRoadmapStep.user_id == uuid.UUID(user_id))
        steps = (await db.execute(road_q)).scalars().all()
        for s in steps:
            items.append({
                "type": "OPPORTUNITY_STEP",
                "id": str(s.id),
                "timestamp": s.created_at.isoformat(),
                "actor_id": str(s.user_id) if s.user_id else None,
                "actor_name": s.user.full_name if s.user else "Agent",
                "title": f"{s.user.first_name if s.user else 'Agent'} added roadmap milestone: '{s.step_type}'",
                "subtitle": s.contact.full_name if s.contact else None,
                "outcome": s.status,
                "notes": s.notes,
                "details": f"Step #{s.step_order}",
                "link": f"/opportunities",
            })

    # 5. Lead Assignments from Audit Logs
    if not activity_type or activity_type in ["ASSIGNMENT", "ALL"]:
        audit_q = (
            select(AuditLog)
            .where(
                AuditLog.action.in_(["contact.assigned", "lead.bulk_distribution", "task.reassigned"]),
                AuditLog.created_at.between(df, dt),
            )
            .options(selectinload(AuditLog.actor))
            .order_by(AuditLog.created_at.desc())
            .limit(100)
        )
        audit_logs = (await db.execute(audit_q)).scalars().all()
        for a in audit_logs:
            items.append({
                "type": "MANAGEMENT_ACTION",
                "id": str(a.id),
                "timestamp": a.created_at.isoformat(),
                "actor_id": str(a.actor_id) if a.actor_id else None,
                "actor_name": a.actor.full_name if a.actor else "Management",
                "title": f"Action: {a.action.replace('.', ' ').title()}",
                "subtitle": f"Entity: {a.entity_type}",
                "outcome": "AUDITED",
                "notes": a.notes or (f"New value: {a.new_value}" if a.new_value else None),
                "details": f"By: {a.actor.full_name if a.actor else 'System'}",
                "link": "/admin/audit-logs",
            })

    # Sort unified feed by timestamp descending
    items.sort(key=lambda x: x["timestamp"], reverse=True)

    total_count = len(items)
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_items = items[start_idx:end_idx]

    return {
        "data": paginated_items,
        "meta": {
            "total": total_count,
            "page": page,
            "per_page": per_page,
            "total_pages": math.ceil(total_count / per_page) if total_count > 0 else 1,
        }
    }

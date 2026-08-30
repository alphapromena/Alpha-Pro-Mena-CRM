"""
Seed script for local development and testing.
Seeds the 4 real Alpha Pro MENA user accounts (Saleh, Hassan, Amin, Ghaida)
plus system admin and team accounts. Automation rules and sample data included.

Temporary passwords are printed to stdout ONCE at seed time — save them immediately.
"""
import asyncio
import secrets
from datetime import datetime, timezone, timedelta
import structlog
from sqlalchemy import select

from app.config import get_settings
from app.database import AsyncSessionLocal, engine, Base
from app.core.security import hash_password, normalize_email, normalize_phone
from app.models.user import User, Team, UserRole
from app.models.company import Company
from app.models.contact import Contact, ContactStatus, ContactPriority
from app.models.call import Call, CallOutcome
from app.models.task import Task, TaskType, TaskStatus, TaskPriority
from app.models.follow_up import FollowUp, FollowUpType
from app.models.recall import Recall
from app.models.no_answer import NoAnswerQueue
from app.models.demo import Demo, DemoStage
from app.models.opportunity import Opportunity, OpportunityStage
from app.models.note import ContactNote
from app.models.campaign import Campaign, CampaignStatus
from app.models.automation import AutomationRule
from app.models.integrations import GoogleSheetsSyncConfig, LeadDistributionRule

logger = structlog.get_logger(__name__)
settings = get_settings()


async def seed_data():
    async with engine.begin() as conn:
        # Create all tables if not exist (convenient for local sqlite/postgres before alembic)
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        # Check if already seeded (using the real Qusai account as sentinel)
        admin_check = (await db.execute(select(User).where(User.email == "qusai@alphapromena.com"))).scalar_one_or_none()
        if admin_check:
            logger.info("seed.already_seeded")
            return

        logger.info("seed.starting")

        # 1. Teams
        team_mena = Team(name="MENA Enterprise Sales", description="High-tier enterprise accounts across UAE, Saudi, Qatar")
        team_saudi = Team(name="Saudi Financial & Banking", description="Specialized Saudi BFSI accounts & fintechs")
        team_gov = Team(name="Gulf Public Sector", description="Governmental & semi-gov organizations")
        db.add_all([team_mena, team_saudi, team_gov])
        await db.flush()

        # 2. Users
        # ── System / Dev account (kept for development access)
        admin_password = settings.admin_password or secrets.token_urlsafe(12)
        dev_admin = User(
            email=settings.admin_email,
            normalized_email=normalize_email(settings.admin_email),
            first_name=settings.admin_first_name,
            last_name=settings.admin_last_name,
            password_hash=hash_password(admin_password),
            role=UserRole.TEAM_LEAD,
            lead_capacity=1000,
        )

        # ── Real Team Lead
        tmp_qusai = secrets.token_urlsafe(12)
        qusai = User(
            email="qusai@alphapromena.com",
            normalized_email=normalize_email("qusai@alphapromena.com"),
            first_name="Qusai",
            last_name="Al-Saleh",
            password_hash=hash_password(tmp_qusai),
            role=UserRole.TEAM_LEAD,
            lead_capacity=1000,
        )

        # ── Real Manager placeholder (uses dev admin email pattern for now)
        tmp_manager = secrets.token_urlsafe(12)
        manager = User(
            email="manager@alphapro.com",
            normalized_email=normalize_email("manager@alphapro.com"),
            first_name="Nour",
            last_name="Haddad",
            password_hash=hash_password(tmp_manager),
            role=UserRole.MANAGER,
            team_id=None,  # set after team flush
            lead_capacity=800,
        )

        # ── 4 Real Sales Users
        tmp_saleh = secrets.token_urlsafe(12)
        saleh = User(
            email="saleh@alphapromena.com",
            normalized_email=normalize_email("saleh@alphapromena.com"),
            first_name="Saleh",
            last_name="",
            password_hash=hash_password(tmp_saleh),
            role=UserRole.USER,
            lead_capacity=500,
        )

        tmp_hassan = secrets.token_urlsafe(12)
        hassan = User(
            email="hassan@alphapromena.com",
            normalized_email=normalize_email("hassan@alphapromena.com"),
            first_name="Hassan",
            last_name="",
            password_hash=hash_password(tmp_hassan),
            role=UserRole.USER,
            lead_capacity=500,
        )

        tmp_amin = secrets.token_urlsafe(12)
        amin = User(
            email="amin@alphapromena.com",
            normalized_email=normalize_email("amin@alphapromena.com"),
            first_name="Amin",
            last_name="",
            password_hash=hash_password(tmp_amin),
            role=UserRole.USER,
            lead_capacity=500,
        )

        tmp_ghaida = secrets.token_urlsafe(12)
        ghaida = User(
            email="ghaida@alphapromena.com",
            normalized_email=normalize_email("ghaida@alphapromena.com"),
            first_name="Ghaida",
            last_name="",
            password_hash=hash_password(tmp_ghaida),
            role=UserRole.USER,
            lead_capacity=500,
        )

        db.add_all([dev_admin, qusai, manager, saleh, hassan, amin, ghaida])
        await db.flush()

        team_mena.manager_id = manager.id
        team_saudi.manager_id = qusai.id
        team_gov.manager_id = manager.id
        manager.team_id = team_mena.id
        saleh.team_id = team_saudi.id
        hassan.team_id = team_mena.id
        amin.team_id = team_mena.id
        ghaida.team_id = team_gov.id
        db.add_all([team_mena, team_saudi, team_gov, manager, saleh, hassan, amin, ghaida])
        await db.flush()

        # Print temporary credentials to stdout (save these — they are not stored)
        logger.info("\n" + "="*60)
        logger.info("SEED CREDENTIALS — SAVE THESE (shown once only)")
        logger.info("="*60)
        logger.info(f"  qusai@alphapromena.com   : {tmp_qusai}")
        logger.info(f"  saleh@alphapromena.com   : {tmp_saleh}")
        logger.info(f"  hassan@alphapromena.com  : {tmp_hassan}")
        logger.info(f"  amin@alphapromena.com    : {tmp_amin}")
        logger.info(f"  ghaida@alphapromena.com  : {tmp_ghaida}")
        logger.info(f"  {settings.admin_email:<25}: {admin_password}" + ("" if settings.admin_password else " (generated)"))
        logger.info(f"  manager@alphapro.com     : {tmp_manager} (generated)")
        logger.info("="*60 + "\n")

        # 3. Default Automation Rules
        rule_no_answer = AutomationRule(
            name="No Answer -> Retry & Queue",
            description="When call outcome is No Answer, creates a retry entry in No Answer Queue",
            trigger_event="call.outcome.no_answer",
            action_type="create_no_answer_entry",
            action_config={"retry_hours": 168}, # 7 days
            is_active=True,
            created_by=qusai.id,
        )
        rule_email_req = AutomationRule(
            name="Email Requested -> Create Email Task",
            description="Creates an immediate task to send email when requested during a call",
            trigger_event="call.outcome.email_requested",
            action_type="create_task",
            action_config={"title": "Send requested information by email", "task_type": "EMAIL", "priority": "HIGH", "due_offset_hours": 4, "assign_to": "lead_owner"},
            is_active=True,
            created_by=qusai.id,
        )
        rule_whatsapp_req = AutomationRule(
            name="WhatsApp Requested -> Create WhatsApp Task",
            description="Creates an outreach task on WhatsApp when requested",
            trigger_event="call.outcome.whatsapp_requested",
            action_type="create_task",
            action_config={"title": "Send WhatsApp introductory deck", "task_type": "WHATSAPP", "priority": "HIGH", "due_offset_hours": 2, "assign_to": "lead_owner"},
            is_active=True,
            created_by=qusai.id,
        )
        rule_demo_req = AutomationRule(
            name="Demo Requested -> Create Demo Task",
            description="Creates demo scheduling task and updates lead status to DEMO_SCHEDULED",
            trigger_event="call.outcome.demo_requested",
            action_type="create_task",
            action_config={"title": "Schedule Product Demonstration with decision maker", "task_type": "DEMO", "priority": "URGENT", "due_offset_hours": 24, "assign_to": "lead_owner"},
            is_active=True,
            created_by=qusai.id,
        )
        db.add_all([rule_no_answer, rule_email_req, rule_whatsapp_req, rule_demo_req])
        await db.flush()

        # 4. Campaigns
        camp_saudi = Campaign(
            name="Saudi Banking Outreach Q3",
            description="Targeting CIOs & Heads of Digital Transformation across Saudi Commercial Banks",
            target_country="Saudi Arabia",
            target_industry="Banking & Financial Services",
            owner_id=qusai.id,
            status=CampaignStatus.ACTIVE,
            start_at=datetime.now(timezone.utc) - timedelta(days=15),
            end_at=datetime.now(timezone.utc) + timedelta(days=75),
        )
        camp_uae = Campaign(
            name="UAE Enterprise Tech & Cloud",
            description="Mid-to-large tech enterprises in Dubai & Abu Dhabi",
            target_country="United Arab Emirates",
            target_industry="Information Technology",
            owner_id=manager.id,
            status=CampaignStatus.ACTIVE,
            start_at=datetime.now(timezone.utc) - timedelta(days=30),
            end_at=datetime.now(timezone.utc) + timedelta(days=60),
        )
        camp_qatar = Campaign(
            name="Qatar Public Sector Modernization",
            description="Outreach to Qatar governmental and regulatory agencies",
            target_country="Qatar",
            target_industry="Government & Public Sector",
            owner_id=qusai.id,
            status=CampaignStatus.ACTIVE,
            start_at=datetime.now(timezone.utc) - timedelta(days=5),
            end_at=datetime.now(timezone.utc) + timedelta(days=90),
        )
        db.add_all([camp_saudi, camp_uae, camp_qatar])
        await db.flush()

        # 5. Companies
        comp_alrajhi = Company(name="Al Rajhi Capital", domain="alrajhi.sa", industry="Banking", country="Saudi Arabia", website="https://alrajhicapital.com", account_owner_id=saleh.id)
        comp_riyad = Company(name="Riyad Bank", domain="riyadbank.com", industry="Banking", country="Saudi Arabia", website="https://riyadbank.com", account_owner_id=saleh.id)
        comp_enbd = Company(name="Emirates NBD", domain="emiratesnbd.com", industry="Financial Services", country="United Arab Emirates", website="https://emiratesnbd.com", account_owner_id=amin.id)
        comp_qnb = Company(name="QNB Group", domain="qnb.com", industry="Banking", country="Qatar", website="https://qnb.com", account_owner_id=amin.id)
        comp_stc = Company(name="stc Solutions", domain="solutions.com.sa", industry="Telecom & Tech", country="Saudi Arabia", website="https://solutions.com.sa", account_owner_id=saleh.id)
        comp_etisalat = Company(name="e& enterprise", domain="eandenterprise.com", industry="Telecom", country="United Arab Emirates", website="https://eandenterprise.com", account_owner_id=amin.id)
        comp_aramco = Company(name="Aramco Digital", domain="aramcodigital.com", industry="Oil & Gas / Tech", country="Saudi Arabia", website="https://aramcodigital.com", account_owner_id=saleh.id)
        db.add_all([comp_alrajhi, comp_riyad, comp_enbd, comp_qnb, comp_stc, comp_etisalat, comp_aramco])
        await db.flush()

        # 6. Contacts
        now = datetime.now(timezone.utc)
        c1 = Contact(
            first_name="Faisal", last_name="Al-Otaibi", company_id=comp_alrajhi.id,
            position="Chief Technology Officer", department="Technology & Innovation",
            email="f.otaibi@alrajhi.sa", normalized_email=normalize_email("f.otaibi@alrajhi.sa"),
            phone="+966501122334", normalized_phone=normalize_phone("+966501122334"),
            country="Saudi Arabia", industry="Banking", source="Saudi Banking Campaign",
            owner_id=saleh.id, team_id=team_saudi.id, campaign_id=camp_saudi.id,
            status=ContactStatus.INTERESTED, priority=ContactPriority.HIGH,
            last_contact_at=now - timedelta(hours=3),
        )
        c2 = Contact(
            first_name="Reem", last_name="Al-Subaie", company_id=comp_riyad.id,
            position="VP of Digital Channels", department="Digital Banking",
            email="reem.subaie@riyadbank.com", normalized_email=normalize_email("reem.subaie@riyadbank.com"),
            phone="+966552233445", normalized_phone=normalize_phone("+966552233445"),
            country="Saudi Arabia", industry="Banking", source="Saudi Banking Campaign",
            owner_id=saleh.id, team_id=team_saudi.id, campaign_id=camp_saudi.id,
            status=ContactStatus.EMAIL_REQUESTED, priority=ContactPriority.URGENT,
            last_contact_at=now - timedelta(days=1),
        )
        c3 = Contact(
            first_name="Rashid", last_name="Al-Nuaimi", company_id=comp_enbd.id,
            position="Head of Enterprise Procurement", department="Procurement",
            email="rashid.n@emiratesnbd.com", normalized_email=normalize_email("rashid.n@emiratesnbd.com"),
            phone="+971509988776", normalized_phone=normalize_phone("+971509988776"),
            country="United Arab Emirates", industry="Financial Services", source="UAE Tech Campaign",
            owner_id=amin.id, team_id=team_mena.id, campaign_id=camp_uae.id,
            status=ContactStatus.DEMO_SCHEDULED, priority=ContactPriority.HIGH,
            last_contact_at=now - timedelta(days=2),
        )
        c4 = Contact(
            first_name="Hassan", last_name="Al-Kuwari", company_id=comp_qnb.id,
            position="Director of IT Infrastructure", department="IT Operations",
            email="hassan.kuwari@qnb.com", normalized_email=normalize_email("hassan.kuwari@qnb.com"),
            phone="+97455112233", normalized_phone=normalize_phone("+97455112233"),
            country="Qatar", industry="Banking", source="Direct Referral",
            owner_id=amin.id, team_id=team_mena.id, campaign_id=camp_qatar.id,
            status=ContactStatus.NO_ANSWER, priority=ContactPriority.MEDIUM,
            last_contact_at=now - timedelta(days=4),
        )
        c5 = Contact(
            first_name="Majed", last_name="Al-Mutawa", company_id=comp_stc.id,
            position="Senior VP Business Development", department="Commercial Solutions",
            email="mmutawa@solutions.com.sa", normalized_email=normalize_email("mmutawa@solutions.com.sa"),
            phone="+966540011223", normalized_phone=normalize_phone("+966540011223"),
            country="Saudi Arabia", industry="Telecom & Tech", source="Google Sheets Ingestion",
            owner_id=saleh.id, team_id=team_saudi.id, campaign_id=camp_saudi.id,
            status=ContactStatus.RECALL_SCHEDULED, priority=ContactPriority.HIGH,
            last_contact_at=now - timedelta(days=1),
        )
        # Unassigned lead in pool
        c6_unassigned = Contact(
            first_name="Zaid", last_name="Al-Masri", company_id=comp_etisalat.id,
            position="Chief Information Security Officer", department="Cybersecurity",
            email="zaid.masri@eandenterprise.com", normalized_email=normalize_email("zaid.masri@eandenterprise.com"),
            phone="+971556677889", normalized_phone=normalize_phone("+971556677889"),
            country="United Arab Emirates", industry="Telecom", source="Google Sheet Import",
            owner_id=None, team_id=None, campaign_id=camp_uae.id,
            status=ContactStatus.NEW, priority=ContactPriority.MEDIUM,
        )
        c7_unassigned = Contact(
            first_name="Khaled", last_name="Al-Shehri", company_id=comp_aramco.id,
            position="Head of Software Architecture", department="Digital Innovation",
            email="khaled.shehri@aramcodigital.com", normalized_email=normalize_email("khaled.shehri@aramcodigital.com"),
            phone="+966567788990", normalized_phone=normalize_phone("+966567788990"),
            country="Saudi Arabia", industry="Oil & Gas / Tech", source="Google Sheet Import",
            owner_id=None, team_id=None, campaign_id=camp_saudi.id,
            status=ContactStatus.NEW, priority=ContactPriority.HIGH,
        )

        db.add_all([c1, c2, c3, c4, c5, c6_unassigned, c7_unassigned])
        await db.flush()

        # 7. Calls history
        call1 = Call(contact_id=c1.id, user_id=saleh.id, outcome=CallOutcome.INTERESTED, duration_seconds=340, notes="Discussed Alpha Pro CRM platform. Very interested in regional compliance & WhatsApp integration.", called_at=now - timedelta(hours=3))
        call2 = Call(contact_id=c2.id, user_id=saleh.id, outcome=CallOutcome.EMAIL_REQUESTED, duration_seconds=120, notes="Requested full product brochure and commercial proposal outline by email.", called_at=now - timedelta(days=1))
        call3 = Call(contact_id=c3.id, user_id=amin.id, outcome=CallOutcome.DEMO_REQUESTED, duration_seconds=420, notes="Scheduled live demonstration for procurement team.", called_at=now - timedelta(days=2))
        call4 = Call(contact_id=c4.id, user_id=amin.id, outcome=CallOutcome.NO_ANSWER, duration_seconds=0, notes="First call attempt - rang with no answer.", called_at=now - timedelta(days=4))
        call5 = Call(contact_id=c5.id, user_id=saleh.id, outcome=CallOutcome.CALL_LATER, duration_seconds=45, notes="In a meeting. Requested callback tomorrow at 11:00 AM.", called_at=now - timedelta(days=1), callback_requested_at=now + timedelta(hours=2))
        db.add_all([call1, call2, call3, call4, call5])

        # 8. Tasks & Recalls
        t1 = Task(
            title="Follow-up with Faisal Al-Otaibi on API capabilities",
            description="Send technical integration spec for core banking APIs.",
            contact_id=c1.id, assigned_to=saleh.id, created_by=saleh.id,
            type=TaskType.FOLLOW_UP, priority=TaskPriority.HIGH, status=TaskStatus.OPEN,
            due_at=now + timedelta(hours=4),
        )
        t2 = Task(
            title="Send Email requested by Reem Al-Subaie",
            description="Include Saudi localized case studies and SLA agreement.",
            contact_id=c2.id, assigned_to=saleh.id, created_by=saleh.id,
            type=TaskType.EMAIL, priority=TaskPriority.URGENT, status=TaskStatus.OPEN,
            due_at=now + timedelta(hours=1),
        )
        t3_overdue = Task(
            title="Review initial NDA document",
            description="Verify draft agreement with legal team.",
            contact_id=c3.id, assigned_to=amin.id, created_by=amin.id,
            type=TaskType.PROPOSAL, priority=TaskPriority.MEDIUM, status=TaskStatus.OVERDUE,
            due_at=now - timedelta(days=1),
        )
        db.add_all([t1, t2, t3_overdue])

        # Recall
        recall1 = Recall(
            contact_id=c5.id, user_id=saleh.id,
            scheduled_at=now + timedelta(hours=2),
            notes="Majed Al-Mutawa requested call back regarding enterprise pricing tiers.",
            status="PENDING",
        )
        db.add(recall1)

        # No Answer Queue Entry
        na1 = NoAnswerQueue(
            contact_id=c4.id, user_id=amin.id, attempt_number=1,
            last_attempt_at=now - timedelta(days=4),
            next_attempt_at=now + timedelta(days=3),
            status="PENDING",
        )
        db.add(na1)

        # 9. Demos & Opportunities
        demo1 = Demo(
            contact_id=c3.id, company_id=comp_enbd.id, owner_id=amin.id,
            stage=DemoStage.SCHEDULED, scheduled_at=now + timedelta(days=2),
            notes="Demo focus: High-volume outreach, analytics dashboard, automated call queues.",
        )
        db.add(demo1)

        opp1 = Opportunity(
            title="Al Rajhi Capital — Enterprise CRM Implementation",
            contact_id=c1.id, company_id=comp_alrajhi.id, owner_id=saleh.id,
            value=45000.0, stage=OpportunityStage.QUALIFIED, probability=60,
            expected_close_at=now + timedelta(days=45),
        )
        opp2 = Opportunity(
            title="Emirates NBD — Sales Outreach Management Platform",
            contact_id=c3.id, company_id=comp_enbd.id, owner_id=amin.id,
            value=65000.0, stage=OpportunityStage.DEMO, probability=50,
            expected_close_at=now + timedelta(days=60),
        )
        db.add_all([opp1, opp2])

        # 10. Google Sheets Sync Config (pre-configured template)
        sheets_cfg = GoogleSheetsSyncConfig(
            name="Saudi Inbound Leads Sheet",
            spreadsheet_id="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
            sheet_name="Inbound Leads",
            range="A:Z",
            column_mapping={
                "first_name": "First Name",
                "last_name": "Last Name",
                "email": "Email Address",
                "phone": "Mobile Number",
                "company": "Company Name",
                "position": "Job Title",
                "country": "Country",
                "industry": "Industry",
                "source": "Lead Source",
            },
            campaign_id=camp_saudi.id,
            is_active=True,
            sync_every_minutes=30,
            created_by=qusai.id,
        )
        db.add(sheets_cfg)

        await db.commit()
        logger.info("seed.completed_successfully")


if __name__ == "__main__":
    asyncio.run(seed_data())

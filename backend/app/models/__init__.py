"""
Models package — import all models so Alembic can detect them.
"""
from app.models.base import TimestampMixin, UUIDMixin, SoftDeleteMixin
from app.models.user import User, Team, UserRole
from app.models.company import Company
from app.models.contact import Contact, ContactStatus, ContactPriority
from app.models.call import Call, CallOutcome
from app.models.note import Note, ContactNote
from app.models.task import Task, TaskType, TaskStatus, TaskPriority
from app.models.follow_up import FollowUp, FollowUpType
from app.models.recall import Recall
from app.models.no_answer import NoAnswerQueue
from app.models.demo import Demo, DemoStage
from app.models.opportunity import Opportunity, OpportunityStage
from app.models.campaign import Campaign, CampaignContact, CampaignStatus
from app.models.audit import AuditLog
from app.models.notification import Notification
from app.models.automation import AutomationRule, AutomationExecution
from app.models.integrations import (
    GoogleSheetsSyncConfig,
    GoogleSheetsSyncRun,
    SyncErrorLog,
    LeadDistributionRule,
    LeadAssignment,
    SavedFilter,
)
from app.models.activity import EmailActivity, WhatsAppActivity

__all__ = [
    "TimestampMixin", "UUIDMixin", "SoftDeleteMixin",
    "User", "Team", "UserRole",
    "Company",
    "Contact", "ContactStatus", "ContactPriority",
    "Call", "CallOutcome",
    "Note", "ContactNote",
    "Task", "TaskType", "TaskStatus", "TaskPriority",
    "FollowUp", "FollowUpType",
    "Recall",
    "NoAnswerQueue",
    "Demo", "DemoStage",
    "Opportunity", "OpportunityStage",
    "Campaign", "CampaignContact", "CampaignStatus",
    "AuditLog",
    "Notification",
    "AutomationRule", "AutomationExecution",
    "GoogleSheetsSyncConfig", "GoogleSheetsSyncRun", "SyncErrorLog",
    "LeadDistributionRule", "LeadAssignment", "SavedFilter",
    "EmailActivity", "WhatsAppActivity",
]

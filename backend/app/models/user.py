"""
User and Team models — authentication, roles, teams.
"""
import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import SoftDeleteMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.contact import Contact
    from app.models.task import Task
    from app.models.audit import AuditLog
    from app.models.notification import Notification


class UserRole(str, PyEnum):
    USER = "USER"
    MANAGER = "MANAGER"
    TEAM_LEAD = "TEAM_LEAD"
    DATA_OPS = "DATA_OPS"

    # Backward compatibility aliases
    ADMIN = "TEAM_LEAD"
    TEAM_LEADER = "TEAM_LEAD"
    SALES_USER = "USER"


class Team(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "teams"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # use_alter marks the users<->teams cycle as intentional so create/drop ordering
    # and Alembic autogenerate handle it (FK is added after both tables exist).
    manager_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL", use_alter=True, name="fk_teams_manager_id_users"),
        nullable=True,
    )

    # Relationships
    manager: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[manager_id], back_populates="managed_team"
    )
    members: Mapped[List["User"]] = relationship(
        "User", foreign_keys="User.team_id", back_populates="team"
    )


class User(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    normalized_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(String(20), nullable=False, default=UserRole.USER)
    team_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("teams.id", ondelete="SET NULL"), nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    login_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    lead_capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=500)
    theme_preference: Mapped[str] = mapped_column(String(50), nullable=False, default="black_beige")
    preferred_language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    team: Mapped[Optional[Team]] = relationship("Team", foreign_keys=[team_id], back_populates="members")
    managed_team: Mapped[Optional[Team]] = relationship("Team", foreign_keys="Team.manager_id", back_populates="manager")
    owned_contacts: Mapped[List["Contact"]] = relationship("Contact", foreign_keys="Contact.owner_id", back_populates="owner")
    assigned_tasks: Mapped[List["Task"]] = relationship("Task", foreign_keys="Task.assigned_to", back_populates="assignee")
    audit_logs: Mapped[List["AuditLog"]] = relationship("AuditLog", back_populates="actor")
    notifications: Mapped[List["Notification"]] = relationship("Notification", back_populates="user")

    @property
    def full_name(self) -> str:
        """Internal system employee display name: strictly first name only."""
        return self.first_name

    @property
    def display_name(self) -> str:
        return self.first_name

    @property
    def is_team_lead(self) -> bool:
        return self.role in (UserRole.TEAM_LEAD, "TEAM_LEAD", "ADMIN", "TEAM_LEADER")

    @property
    def is_team_lead_or_above(self) -> bool:
        return self.is_team_lead

    @property
    def is_team_leader_or_above(self) -> bool:
        return self.is_team_lead

    @property
    def is_manager_or_above(self) -> bool:
        return self.role in (UserRole.TEAM_LEAD, UserRole.MANAGER, "TEAM_LEAD", "MANAGER", "ADMIN", "TEAM_LEADER")

    @property
    def is_admin(self) -> bool:
        return self.is_team_lead

    @property
    def is_user(self) -> bool:
        return self.role in (UserRole.USER, "USER", "SALES_USER")

    @property
    def is_data_ops(self) -> bool:
        return self.role in (UserRole.DATA_OPS, "DATA_OPS")

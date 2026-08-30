"""
Database automatic role and schema migration utilities.
Safely migrates legacy roles (ADMIN, TEAM_LEADER, SALES_USER) to (TEAM_LEAD, MANAGER, USER)
and ensures the primary Team Lead (Qusai) is seeded and accessible.
"""
import structlog
from sqlalchemy import select, update, or_
from app.database import AsyncSessionLocal
from app.core.security import hash_password, normalize_email
from app.models.user import User, UserRole

logger = structlog.get_logger(__name__)


async def run_role_migrations():
    """Ensure database user roles match the 3-role operational hierarchy: USER, MANAGER, TEAM_LEAD."""
    async with AsyncSessionLocal() as db:
        try:
            # 1. Migrate legacy role names
            await db.execute(
                update(User)
                .where(User.role.in_(["ADMIN", "TEAM_LEADER"]))
                .values(role=UserRole.TEAM_LEAD)
            )
            await db.execute(
                update(User)
                .where(User.role == "SALES_USER")
                .values(role=UserRole.USER)
            )

            # 2. Ensure primary Team Lead (Qusai) exists
            qusai_res = await db.execute(select(User).where(User.email == "qusai@alphapro.com"))
            qusai = qusai_res.scalar_one_or_none()

            if not qusai:
                qusai = User(
                    email="qusai@alphapro.com",
                    normalized_email=normalize_email("qusai@alphapro.com"),
                    first_name="Qusai",
                    last_name="Al-Saleh",
                    password_hash=hash_password("<set-password>"),
                    role=UserRole.TEAM_LEAD,
                    lead_capacity=1000,
                )
                db.add(qusai)
                logger.info("migration.qusai_team_lead_created")
            else:
                qusai.role = UserRole.TEAM_LEAD
                qusai.first_name = "Qusai"
                qusai.is_active = True
                db.add(qusai)

            # 3. Ensure admin@alphapro.com is also migrated to TEAM_LEAD
            admin_res = await db.execute(select(User).where(User.email == "admin@alphapro.com"))
            admin_user = admin_res.scalar_one_or_none()
            if admin_user:
                admin_user.role = UserRole.TEAM_LEAD
                db.add(admin_user)

            await db.commit()
            logger.info("migration.roles_migrated_successfully")
        except Exception as e:
            await db.rollback()
            logger.error("migration.failed", error=str(e))

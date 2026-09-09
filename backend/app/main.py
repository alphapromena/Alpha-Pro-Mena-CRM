"""
Alpha Pro MENA CRM — FastAPI Application Factory
"""
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from starlette.exceptions import HTTPException

from app.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging
from app.core.ratelimit import limiter, rate_limit_handler
from app.middleware.error_handler import (
    app_error_handler,
    generic_error_handler,
    http_exception_handler,
    validation_error_handler,
)
from app.middleware.logging import RequestContextMiddleware

# Import all routers
from app.auth.router import router as auth_router

settings = get_settings()
configure_logging()
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    logger.info(
        "crm.startup",
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.app_env,
        serverless=settings.is_serverless,
        scheduler=settings.scheduler_enabled,
        google_sheets_enabled=settings.google_sheets_enabled,
    )

    # Auto-migrate schema and bootstrap team accounts if needed
    try:
        from app.database import AsyncSessionLocal
        from app.core.auto_migrate import auto_migrate_if_needed
        async with AsyncSessionLocal() as session:
            await auto_migrate_if_needed(session)
    except Exception as exc:
        logger.error("crm.startup.migrate_error", error=str(exc))

    # In-process scheduler only on long-running servers; on Vercel, crons hit /api/v1/jobs/*
    if settings.scheduler_enabled:
        from app.jobs.scheduler import start_scheduler
        await start_scheduler()

    yield

    if settings.scheduler_enabled:
        from app.jobs.scheduler import stop_scheduler
        await stop_scheduler()
    logger.info("crm.shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Alpha Pro MENA CRM & Sales Outreach Management System",
        docs_url="/api/docs" if settings.app_debug else None,
        redoc_url="/api/redoc" if settings.app_debug else None,
        openapi_url="/api/openapi.json" if settings.app_debug else None,
        lifespan=lifespan,
    )

    # ── Rate limiting ────────────────────────────────────────────────────────
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

    # ── CORS ─────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    # ── Custom Middleware ─────────────────────────────────────────────────────
    app.add_middleware(RequestContextMiddleware)

    # ── Exception Handlers ───────────────────────────────────────────────────
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, generic_error_handler)

    # ── Routers ──────────────────────────────────────────────────────────────
    prefix = "/api/v1"
    app.include_router(auth_router, prefix=prefix)
    _register_routers(app, prefix)

    # ── Health Check ─────────────────────────────────────────────────────────
    @app.get("/api/health", tags=["Health"])
    async def health():
        from app.database import engine

        db_status = "ok"
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception as exc:  # report, never crash the probe
            logger.error("health.db_unreachable", error=str(exc))
            db_status = "unreachable"
        return {
            "status": "ok" if db_status == "ok" else "degraded",
            "version": settings.app_version,
            "database": db_status,
        }

    return app


def _register_routers(app: FastAPI, prefix: str) -> None:
    """Register all domain routers."""
    from app.users.router import router as users_router
    from app.teams.router import router as teams_router
    from app.contacts.router import router as contacts_router
    from app.companies.router import router as companies_router
    from app.calls.router import router as calls_router
    from app.tasks.router import router as tasks_router
    from app.follow_ups.router import router as follow_ups_router
    from app.recalls.router import router as recalls_router
    from app.no_answer.router import router as no_answer_router
    from app.demos.router import router as demos_router
    from app.opportunities.router import router as opportunities_router
    from app.campaigns.router import router as campaigns_router
    from app.notifications.router import router as notifications_router
    from app.audit.router import router as audit_router
    from app.automation.router import router as automation_router
    from app.search.router import router as search_router
    from app.reports.router import router as reports_router
    from app.admin.router import router as admin_router
    from app.integrations.google_sheets.router import router as sheets_router
    from app.jobs.router import router as jobs_router

    for router in [
        users_router, teams_router, contacts_router, companies_router,
        calls_router, tasks_router, follow_ups_router, recalls_router,
        no_answer_router, demos_router, opportunities_router, campaigns_router,
        notifications_router, audit_router, automation_router, search_router,
        reports_router, admin_router, sheets_router, jobs_router,
    ]:
        app.include_router(router, prefix=prefix)


app = create_app()

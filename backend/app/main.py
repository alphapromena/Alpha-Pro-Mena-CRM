"""
Alpha Pro MENA CRM — FastAPI Application Factory
"""
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException

from app.config import get_settings
from app.core.logging import configure_logging
from app.middleware.error_handler import (
    app_error_handler,
    generic_error_handler,
    http_exception_handler,
    validation_error_handler,
)
from app.middleware.logging import RequestContextMiddleware
from app.core.exceptions import AppError

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
        google_sheets_enabled=settings.google_sheets_enabled,
    )

    # Run automated role hierarchy migration & ensure primary Team Lead Qusai
    from app.migrations import run_role_migrations
    await run_role_migrations()

    # Start background job scheduler
    from app.jobs.scheduler import start_scheduler, stop_scheduler
    await start_scheduler()

    yield

    # Graceful shutdown
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

    # Import and register remaining routers
    _register_routers(app, prefix)

    # ── Health Check ─────────────────────────────────────────────────────────
    @app.get("/api/health", tags=["Health"])
    async def health():
        return {"status": "ok", "version": settings.app_version}

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

    for router in [
        users_router, teams_router, contacts_router, companies_router,
        calls_router, tasks_router, follow_ups_router, recalls_router,
        no_answer_router, demos_router, opportunities_router, campaigns_router,
        notifications_router, audit_router, automation_router, search_router,
        reports_router, admin_router, sheets_router,
    ]:
        app.include_router(router, prefix=prefix)


app = create_app()

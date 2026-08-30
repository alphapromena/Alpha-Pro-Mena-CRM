"""
Error handler middleware — centralized exception → JSON response mapping.
Never exposes stack traces to clients.
"""
import structlog
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

from app.core.exceptions import AppError

logger = structlog.get_logger(__name__)


def error_response(
    status_code: int,
    error_code: str,
    message: str,
    details: list = None,
    request_id: str = None,
) -> JSONResponse:
    content = {
        "error": {
            "code": error_code,
            "message": message,
            "details": details or [],
        },
        "meta": {"request_id": request_id},
    }
    return JSONResponse(status_code=status_code, content=content)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    logger.warning(
        "app_error",
        error_code=exc.error_code,
        message=exc.message,
        path=request.url.path,
    )
    return error_response(
        status_code=exc.status_code,
        error_code=exc.error_code,
        message=exc.message,
        details=exc.details,
        request_id=request.headers.get("X-Request-ID"),
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"] if loc != "body")
        details.append({"field": field, "message": error["msg"]})

    logger.info("validation_error", path=request.url.path, details=details)
    return error_response(
        status_code=422,
        error_code="VALIDATION_ERROR",
        message="Request validation failed.",
        details=details,
        request_id=request.headers.get("X-Request-ID"),
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return error_response(
        status_code=exc.status_code,
        error_code="HTTP_ERROR",
        message=str(exc.detail),
        request_id=request.headers.get("X-Request-ID"),
    )


async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "unhandled_exception",
        path=request.url.path,
        exc_type=type(exc).__name__,
    )
    return error_response(
        status_code=500,
        error_code="INTERNAL_ERROR",
        message="An internal server error occurred.",
        request_id=request.headers.get("X-Request-ID"),
    )

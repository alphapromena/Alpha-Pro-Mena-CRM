"""
Centralized exception hierarchy and error handling.
Never expose internal details to API clients.
"""
from typing import Any, Dict, List, Optional


class AppError(Exception):
    """Base exception for all application errors."""
    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"
    message: str = "An internal error occurred."

    def __init__(
        self,
        message: Optional[str] = None,
        details: Optional[List[Dict[str, Any]]] = None,
    ):
        self.message = message or self.__class__.message
        self.details = details or []
        super().__init__(self.message)


class ValidationError(AppError):
    status_code = 400
    error_code = "VALIDATION_ERROR"
    message = "Validation failed."


class NotFoundError(AppError):
    status_code = 404
    error_code = "NOT_FOUND"
    message = "Resource not found."


class ForbiddenError(AppError):
    status_code = 403
    error_code = "FORBIDDEN"
    message = "Access denied."


class UnauthorizedError(AppError):
    status_code = 401
    error_code = "UNAUTHORIZED"
    message = "Authentication required."


class ConflictError(AppError):
    status_code = 409
    error_code = "CONFLICT"
    message = "Resource conflict."


class RateLimitError(AppError):
    status_code = 429
    error_code = "RATE_LIMITED"
    message = "Too many requests. Please slow down."


class DNCError(AppError):
    """Raised when attempting outbound activity to a Do Not Contact contact."""
    status_code = 409
    error_code = "DO_NOT_CONTACT"
    message = "This contact has Do Not Contact status. Outbound activities are blocked."


class AccountLockedError(AppError):
    status_code = 423
    error_code = "ACCOUNT_LOCKED"
    message = "Account is temporarily locked due to too many failed login attempts."

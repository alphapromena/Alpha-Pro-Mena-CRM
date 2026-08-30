"""
Rate limiting (slowapi). Keys on the real client IP, honouring X-Forwarded-For / X-Real-IP
so it works behind Vercel, Nginx or Cloudflare. Disabled under the test environment.
"""
from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import get_settings

settings = get_settings()


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    return get_remote_address(request)


limiter = Limiter(
    key_func=client_ip,
    headers_enabled=False,
    enabled=settings.app_env != "test",
)


async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "error": {
                "code": "RATE_LIMITED",
                "message": f"Too many requests. Limit: {exc.detail}.",
                "details": [],
            },
            "meta": {"request_id": request.headers.get("X-Request-ID")},
        },
        headers={"Retry-After": "60"},
    )
